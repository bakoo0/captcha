const express = require("express");
const path = require("path");
const fs = require("fs");
const { spawn } = require("child_process");

const app = express();
const PORT = process.env.PORT || 3000;

const ROOT = __dirname;
const PUBLIC_DIR = path.join(ROOT, "public");
const WIDGET_DIR = path.join(ROOT, "widget");
const DATA_DIR = path.join(ROOT, "data");
const SCRIPTS_DIR = path.join(ROOT, "scripts");

const INPUT_JSON = path.join(DATA_DIR, "tmp_request.json");
const OUTPUT_JSON = path.join(DATA_DIR, "tmp_response.json");
const EVENTS_CSV = path.join(DATA_DIR, "behavior_events_runtime.csv");

app.use(express.json({ limit: "5mb" }));
app.use(express.urlencoded({ extended: true }));

app.use("/widget", express.static(WIDGET_DIR));
app.use(express.static(PUBLIC_DIR));

function ensureDir(dirPath) {
  if (!fs.existsSync(dirPath)) {
    fs.mkdirSync(dirPath, { recursive: true });
  }
}

function ensureRuntimeCsv() {
  ensureDir(DATA_DIR);

  if (!fs.existsSync(EVENTS_CSV)) {
    fs.writeFileSync(
      EVENTS_CSV,
      "session_id,event_type,timestamp_ms,x,y,scroll_y,key,target\n",
      "utf8"
    );
  }
}

function appendEventsToCsv(sessionId, events) {
  ensureRuntimeCsv();

  if (!Array.isArray(events) || events.length === 0) return;

  const rows = events.map((e) => {
    const esc = (v) => `"${String(v ?? "").replace(/"/g, '""')}"`;

    return [
      esc(sessionId || ""),
      esc(e.type || ""),
      Number.isFinite(Number(e.t)) ? Number(e.t) : "",
      Number.isFinite(Number(e.x)) ? Number(e.x) : "",
      Number.isFinite(Number(e.y)) ? Number(e.y) : "",
      Number.isFinite(Number(e.scrollY)) ? Number(e.scrollY) : "",
      esc(e.key || ""),
      esc(e.target || "")
    ].join(",");
  });

  fs.appendFileSync(EVENTS_CSV, rows.join("\n") + "\n", "utf8");
}

function fallbackRisk(events) {
  const totalEvents = Array.isArray(events) ? events.length : 0;

  let score = 0.15;
  if (totalEvents < 8) score += 0.40;
  else if (totalEvents < 20) score += 0.20;

  if (score > 0.99) score = 0.99;

  let decision = "allow";
  if (score > 0.7) decision = "hard_captcha";
  else if (score > 0.3) decision = "show_captcha";

  return {
    score: Number(score.toFixed(4)),
    decision,
    features: {
      total_events: totalEvents
    },
    model_source: "fallback"
  };
}

function runPythonInference(payload) {
  return new Promise((resolve, reject) => {
    ensureDir(DATA_DIR);

    const inferencePath = path.join(SCRIPTS_DIR, "inference.py");
    if (!fs.existsSync(inferencePath)) {
      reject(new Error("inference.py not found"));
      return;
    }

    fs.writeFileSync(INPUT_JSON, JSON.stringify(payload, null, 2), "utf8");

    if (fs.existsSync(OUTPUT_JSON)) {
      fs.unlinkSync(OUTPUT_JSON);
    }

    const pythonCmd = process.platform === "win32" ? "python" : "python3";

    const child = spawn(
      pythonCmd,
      [inferencePath, "--input", INPUT_JSON, "--output", OUTPUT_JSON],
      {
        cwd: ROOT
      }
    );

    let stdout = "";
    let stderr = "";

    child.stdout.on("data", (chunk) => {
      stdout += chunk.toString();
    });

    child.stderr.on("data", (chunk) => {
      stderr += chunk.toString();
    });

    child.on("error", (err) => {
      reject(err);
    });

    child.on("close", (code) => {
      if (code !== 0) {
        reject(new Error(`Python exited with code ${code}. ${stderr || stdout}`));
        return;
      }

      if (!fs.existsSync(OUTPUT_JSON)) {
        reject(new Error("Python output file was not created"));
        return;
      }

      try {
        const raw = fs.readFileSync(OUTPUT_JSON, "utf8");
        const parsed = JSON.parse(raw);
        resolve(parsed);
      } catch (err) {
        reject(err);
      }
    });
  });
}

app.get("/", (_req, res) => {
  res.sendFile(path.join(PUBLIC_DIR, "index.html"));
});

app.get("/api/health", (_req, res) => {
  res.json({
    ok: true,
    port: PORT,
    files: {
      public_dir_exists: fs.existsSync(PUBLIC_DIR),
      widget_dir_exists: fs.existsSync(WIDGET_DIR),
      scripts_dir_exists: fs.existsSync(SCRIPTS_DIR),
      index_html_exists: fs.existsSync(path.join(PUBLIC_DIR, "index.html")),
      widget_file_exists: fs.existsSync(path.join(WIDGET_DIR, "behavior-captcha-widget.js")),
      inference_exists: fs.existsSync(path.join(SCRIPTS_DIR, "inference.py")),
      model_exists: fs.existsSync(path.join(SCRIPTS_DIR, "bot_detector_bundle.joblib"))
    }
  });
});

app.post("/api/risk-score", async (req, res) => {
  try {
    const sessionId = req.body?.sessionId || `sess_${Date.now()}`;
    const events = Array.isArray(req.body?.events) ? req.body.events : [];
    const meta = req.body?.meta || {};

    appendEventsToCsv(sessionId, events);

    const payload = {
      sessionId,
      events,
      meta
    };

    try {
      const result = await runPythonInference(payload);

      res.json({
        ok: true,
        source: "python",
        sessionId,
        ...result
      });
      return;
    } catch (pythonError) {
      console.error("Python inference failed:", pythonError);

      const fallback = fallbackRisk(events);

      res.json({
        ok: true,
        source: "fallback",
        sessionId,
        python_error: String(pythonError.message || pythonError),
        ...fallback
      });
    }
  } catch (error) {
    console.error("POST /api/risk-score failed:", error);
    res.status(500).json({
      ok: false,
      error: String(error.message || error)
    });
  }
});

ensureRuntimeCsv();

app.listen(PORT, () => {
  console.log(`Server running on http://localhost:${PORT}`);
});