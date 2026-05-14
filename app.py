import csv
import json
import math
import os
import random
import time
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional

import joblib
import numpy as np
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from pymongo import MongoClient


load_dotenv()

ROOT = Path(__file__).resolve().parent

MODEL_PATH = ROOT / "scripts" / "bot_detector_bundle.joblib"
PAREIDOLIA_PATH = ROOT / "data" / "pareidolia_pool.json"
RUNTIME_CSV_PATH = ROOT / "data" / "runtime_sessions.csv"

MONGO_URI = os.getenv("MONGO_URI", "")
MONGO_DB = os.getenv("MONGO_DB", "adaptive_captcha")


mongo_client = None
mongo_db = None


def is_mongodb_connected() -> bool:
    if mongo_client is None:
        return False

    try:
        mongo_client.admin.command("ping")
        return True
    except Exception:
        return False


if MONGO_URI:
    try:
        mongo_client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=5000)
        mongo_client.admin.command("ping")
        mongo_db = mongo_client[MONGO_DB]
        print("MongoDB connected successfully.")
    except Exception as error:
        print("MongoDB connection failed:", error)
        mongo_client = None
        mongo_db = None


app = FastAPI(title="Adaptive CAPTCHA API")


app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


app.mount("/widget", StaticFiles(directory=str(ROOT / "widget")), name="widget")
app.mount("/static", StaticFiles(directory=str(ROOT / "static")), name="static")


class RiskRequest(BaseModel):
    sessionId: Optional[str] = None
    siteKey: Optional[str] = "unknown-site"
    events: List[Dict[str, Any]] = Field(default_factory=list)
    meta: Dict[str, Any] = Field(default_factory=dict)


class CaptchaVerifyRequest(BaseModel):
    sessionId: str
    challengeId: str
    selectedIds: List[str] = Field(default_factory=list)
    captchaEvents: Optional[List[Dict[str, Any]]] = Field(default_factory=list)


if not MODEL_PATH.exists():
    raise FileNotFoundError(f"ML model not found: {MODEL_PATH}")


model_bundle = joblib.load(MODEL_PATH)

model = model_bundle["model"]
feature_cols = model_bundle["feature_cols"]
model_name = model_bundle.get("model_name", "trained_model")

IN_MEMORY_CHALLENGES: Dict[str, Dict[str, Any]] = {}


def safe_float(value: Any, default: float = 0.0) -> float:
    try:
        if value is None:
            return default
        return float(value)
    except Exception:
        return default


def safe_mean(values: List[float]) -> float:
    values = [v for v in values if isinstance(v, (int, float))]

    if not values:
        return 0.0

    return sum(values) / len(values)


def safe_std(values: List[float]) -> float:
    values = [v for v in values if isinstance(v, (int, float))]

    if len(values) < 2:
        return 0.0

    mean_value = safe_mean(values)
    variance = sum((v - mean_value) ** 2 for v in values) / len(values)

    return math.sqrt(variance)


def extract_features(events: List[Dict[str, Any]]) -> Dict[str, float]:
    mouse_events = [e for e in events if e.get("type") == "mousemove"]
    click_events = [e for e in events if e.get("type") == "click"]
    keydown_events = [e for e in events if e.get("type") == "keydown"]
    keyup_events = [e for e in events if e.get("type") == "keyup"]
    scroll_events = [e for e in events if e.get("type") == "scroll"]
    focus_events = [e for e in events if e.get("type") == "focus"]
    blur_events = [e for e in events if e.get("type") == "blur"]
    captcha_click_events = [e for e in events if e.get("type") == "captcha_click"]

    times = [safe_float(e.get("t")) for e in events if e.get("t") is not None]

    if len(times) >= 2:
        session_start_ms = min(times)
        session_end_ms = max(times)
        duration_ms = max(0.0, session_end_ms - session_start_ms)
    else:
        session_start_ms = 0.0
        session_end_ms = 0.0
        duration_ms = 0.0

    duration_sec = duration_ms / 1000.0 if duration_ms > 0 else 1.0

    mouse_path_len = 0.0
    mouse_displacement = 0.0
    mouse_speeds = []
    mouse_dts = []
    mouse_direction_changes = 0
    mouse_idle_pauses = 0

    mouse_points = []

    for e in mouse_events:
        mouse_points.append(
            (
                safe_float(e.get("t")),
                safe_float(e.get("x")),
                safe_float(e.get("y")),
            )
        )

    if len(mouse_points) >= 2:
        first_t, first_x, first_y = mouse_points[0]
        last_t, last_x, last_y = mouse_points[-1]

        mouse_displacement = math.sqrt(
            (last_x - first_x) ** 2 + (last_y - first_y) ** 2
        )

        previous_angle = None

        for i in range(1, len(mouse_points)):
            prev_t, prev_x, prev_y = mouse_points[i - 1]
            cur_t, cur_x, cur_y = mouse_points[i]

            dx = cur_x - prev_x
            dy = cur_y - prev_y
            dt = cur_t - prev_t
            distance = math.sqrt(dx * dx + dy * dy)

            mouse_path_len += distance

            if dt > 0:
                mouse_dts.append(dt)
                mouse_speeds.append(distance / dt)

            if dt > 1000:
                mouse_idle_pauses += 1

            if distance > 0:
                angle = math.atan2(dy, dx)

                if previous_angle is not None:
                    diff = angle - previous_angle

                    while diff > math.pi:
                        diff -= 2 * math.pi

                    while diff < -math.pi:
                        diff += 2 * math.pi

                    if abs(diff) > 0.6:
                        mouse_direction_changes += 1

                previous_angle = angle

    mouse_straightness = (
        mouse_displacement / mouse_path_len if mouse_path_len > 0 else 0.0
    )

    scroll_values = [safe_float(e.get("scrollY")) for e in scroll_events]
    scroll_deltas = []

    for i in range(1, len(scroll_values)):
        scroll_deltas.append(scroll_values[i] - scroll_values[i - 1])

    scroll_bursts = sum(1 for d in scroll_deltas if abs(d) > 250)

    key_times = [safe_float(e.get("t")) for e in keydown_events]
    interkeys = []

    for i in range(1, len(key_times)):
        interkeys.append(key_times[i] - key_times[i - 1])

    keys = [str(e.get("key", "")) for e in keydown_events]
    backspace_n = sum(1 for k in keys if k.lower() == "backspace")

    focus_jump_total = 0
    previous_target = None

    for e in focus_events:
        target = str(e.get("target", ""))

        if previous_target and target and target != previous_target:
            focus_jump_total += 1

        if target:
            previous_target = target

    features = {
        "n_events": float(len(events)),
        "session_start_ms": float(session_start_ms),
        "session_end_ms": float(session_end_ms),
        "duration_ms": float(duration_ms),

        "mousemove_n": float(len(mouse_events)),
        "mousedown_n": float(len([e for e in events if e.get("type") == "mousedown"])),
        "mouseup_n": float(len([e for e in events if e.get("type") == "mouseup"])),
        "click_n": float(len(click_events)),
        "scroll_event_n": float(len(scroll_events)),
        "keydown_n": float(len(keydown_events)),
        "keyup_n": float(len(keyup_events)),

        "events_per_sec": float(len(events) / duration_sec),
        "clicks_per_sec": float(len(click_events) / duration_sec),
        "keys_per_sec": float(len(keydown_events) / duration_sec),
        "scrolls_per_sec": float(len(scroll_events) / duration_sec),

        "mouse_n": float(len(mouse_events)),
        "mouse_path_len": float(mouse_path_len),
        "mouse_displacement": float(mouse_displacement),
        "mouse_straightness": float(mouse_straightness),
        "mouse_speed_mean": float(safe_mean(mouse_speeds)),
        "mouse_speed_std": float(safe_std(mouse_speeds)),
        "mouse_speed_max": float(max(mouse_speeds) if mouse_speeds else 0.0),
        "mouse_move_dt_mean": float(safe_mean(mouse_dts)),
        "mouse_move_dt_std": float(safe_std(mouse_dts)),
        "mouse_direction_changes": float(mouse_direction_changes),
        "mouse_idle_pauses": float(mouse_idle_pauses),

        "scroll_n": float(len(scroll_events)),
        "scroll_delta_mean": float(safe_mean(scroll_deltas)),
        "scroll_delta_std": float(safe_std(scroll_deltas)),
        "scroll_delta_max": float(
            max([abs(v) for v in scroll_deltas]) if scroll_deltas else 0.0
        ),
        "scroll_bursts": float(scroll_bursts),

        "key_n": float(len(keydown_events)),
        "interkey_mean": float(safe_mean(interkeys)),
        "interkey_std": float(safe_std(interkeys)),
        "backspace_n": float(backspace_n),
        "unique_keys": float(len(set(keys))),

        "focus_n": float(len(focus_events)),
        "blur_n": float(len(blur_events)),
        "focus_jump_total": float(focus_jump_total),

        "captcha_click_n": float(len(captcha_click_events)),
    }

    return features


def predict_risk(events: List[Dict[str, Any]]) -> Dict[str, Any]:
    features = extract_features(events)

    x = np.array(
        [
            [features.get(col, 0.0) for col in feature_cols]
        ]
    )

    if hasattr(model, "predict_proba"):
        score = float(model.predict_proba(x)[0][1])
    else:
        score = float(model.predict(x)[0])

    score = max(0.0, min(1.0, score))

    allow_max = 0.70
    captcha_max = 0.85

    if score <= allow_max:
        decision = "allow"
    elif score <= captcha_max:
        decision = "show_captcha"
    else:
        decision = "hard_captcha"

    return {
        "score": round(score, 4),
        "decision": decision,
        "features": features,
        "thresholds": {
            "allow_max": allow_max,
            "captcha_max": captcha_max
        },
        "model_source": model_name
    }


def save_runtime_csv(
    session_id: str,
    payload: RiskRequest,
    result: Optional[Dict[str, Any]] = None
) -> None:
    RUNTIME_CSV_PATH.parent.mkdir(parents=True, exist_ok=True)

    file_exists = RUNTIME_CSV_PATH.exists()

    with open(RUNTIME_CSV_PATH, "a", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(
            file,
            fieldnames=[
                "session_id",
                "site_key",
                "created_at",
                "risk_score",
                "decision",
                "events_count",
                "user_agent",
                "screen_width",
                "screen_height",
                "viewport_width",
                "viewport_height"
            ]
        )

        if not file_exists:
            writer.writeheader()

        meta = payload.meta or {}

        writer.writerow({
            "session_id": session_id,
            "site_key": payload.siteKey,
            "created_at": int(time.time()),
            "risk_score": result.get("score", "") if result else "",
            "decision": result.get("decision", "") if result else "",
            "events_count": len(payload.events),
            "user_agent": meta.get("userAgent", ""),
            "screen_width": meta.get("screenWidth", ""),
            "screen_height": meta.get("screenHeight", ""),
            "viewport_width": meta.get("viewportWidth", ""),
            "viewport_height": meta.get("viewportHeight", "")
        })


def save_session(session_id: str, payload: RiskRequest, result: Dict[str, Any]) -> None:
    if mongo_db is None:
        save_runtime_csv(session_id, payload, result)
        return

    meta = payload.meta or {}

    mongo_db["sessions"].update_one(
        {"_id": session_id},
        {
            "$set": {
                "site_key": payload.siteKey,
                "created_at": int(time.time()),
                "meta": meta,
                "risk_score": result["score"],
                "decision": result["decision"],
                "thresholds": result["thresholds"],
                "model_source": result["model_source"],
                "features": result["features"],
                "events_count": len(payload.events)
            }
        },
        upsert=True
    )

    if payload.events:
        mongo_db["behavior_events"].insert_many(
            [
                {
                    "session_id": session_id,
                    "site_key": payload.siteKey,
                    "event": event,
                    "created_at": int(time.time())
                }
                for event in payload.events
            ]
        )


def load_pareidolia_pool() -> Dict[str, Any]:
    if not PAREIDOLIA_PATH.exists():
        raise HTTPException(
            status_code=500,
            detail=f"Pareidolia pool file not found: {PAREIDOLIA_PATH}"
        )

    with open(PAREIDOLIA_PATH, "r", encoding="utf-8") as file:
        return json.load(file)


@app.get("/api/health")
def health():
    return {
        "ok": True,
        "model_loaded": MODEL_PATH.exists(),
        "model_source": model_name,
        "mongodb_connected": is_mongodb_connected(),
        "pareidolia_pool_loaded": PAREIDOLIA_PATH.exists()
    }


@app.post("/api/events")
def save_events(payload: RiskRequest):
    session_id = payload.sessionId or f"sess_{uuid.uuid4().hex}"

    try:
        if mongo_db is not None:
            mongo_db["sessions"].update_one(
                {"_id": session_id},
                {
                    "$set": {
                        "site_key": payload.siteKey,
                        "last_event_at": int(time.time()),
                        "meta": payload.meta or {},
                        "events_count": len(payload.events)
                    },
                    "$setOnInsert": {
                        "created_at": int(time.time())
                    }
                },
                upsert=True
            )

            if payload.events:
                mongo_db["behavior_events"].insert_many(
                    [
                        {
                            "session_id": session_id,
                            "site_key": payload.siteKey,
                            "event": event,
                            "created_at": int(time.time())
                        }
                        for event in payload.events
                    ]
                )
        else:
            save_runtime_csv(session_id, payload, None)

        return {
            "ok": True,
            "sessionId": session_id,
            "events_saved": len(payload.events),
            "mongodb_connected": is_mongodb_connected()
        }

    except Exception as error:
        raise HTTPException(status_code=500, detail=str(error))


@app.post("/api/risk-score")
def risk_score(payload: RiskRequest):
    session_id = payload.sessionId or f"sess_{uuid.uuid4().hex}"

    try:
        result = predict_risk(payload.events)
        save_session(session_id, payload, result)

        return {
            "ok": True,
            "sessionId": session_id,
            **result
        }

    except Exception as error:
        raise HTTPException(status_code=500, detail=str(error))


@app.get("/api/captcha/challenge")
def captcha_challenge(sessionId: str, level: str = "medium"):
    pool = load_pareidolia_pool()

    if level not in ["medium", "hard"]:
        level = "medium"

    faces = pool.get("pareidolia_faces", [])
    non_faces = pool.get("non_faces", [])

    if not faces or not non_faces:
        raise HTTPException(status_code=500, detail="Pareidolia image pool is empty")

    if level == "hard":
        correct_count = min(3, len(faces))
        distractor_count = min(6, len(non_faces))
    else:
        correct_count = min(2, len(faces))
        distractor_count = min(4, len(non_faces))

    correct_items = random.sample(faces, correct_count)
    distractor_items = random.sample(non_faces, distractor_count)

    items = []
    correct_ids = []

    for item in correct_items:
        correct_ids.append(item["id"])

        items.append({
            "id": item["id"],
            "src": item["src"],
            "alt": "pareidolia image"
        })

    for item in distractor_items:
        items.append({
            "id": item["id"],
            "src": item["src"],
            "alt": "non-face image"
        })

    random.shuffle(items)

    challenge_id = f"ch_{uuid.uuid4().hex}"

    challenge_doc = {
        "_id": challenge_id,
        "session_id": sessionId,
        "level": level,
        "correct_ids": correct_ids,
        "created_at": int(time.time()),
        "expires_at": int(time.time()) + 300
    }

    IN_MEMORY_CHALLENGES[challenge_id] = challenge_doc

    if mongo_db is not None:
        mongo_db["captcha_challenges"].insert_one(challenge_doc)

    return {
        "ok": True,
        "challengeId": challenge_id,
        "level": level,
        "instruction": "Select all images where you can see a face-like pattern.",
        "items": items
    }


@app.post("/api/captcha/verify")
def captcha_verify(payload: CaptchaVerifyRequest):
    challenge = None

    if mongo_db is not None:
        challenge = mongo_db["captcha_challenges"].find_one(
            {
                "_id": payload.challengeId,
                "session_id": payload.sessionId
            }
        )

    if challenge is None:
        challenge = IN_MEMORY_CHALLENGES.get(payload.challengeId)

    if not challenge:
        raise HTTPException(status_code=404, detail="Challenge not found")

    if int(time.time()) > int(challenge.get("expires_at", 0)):
        raise HTTPException(status_code=400, detail="Challenge expired")

    correct_ids = sorted(challenge["correct_ids"])
    selected_ids = sorted(payload.selectedIds)

    success = correct_ids == selected_ids

    attempt_doc = {
        "challenge_id": payload.challengeId,
        "session_id": payload.sessionId,
        "selected_ids": payload.selectedIds,
        "correct_ids": challenge["correct_ids"],
        "success": success,
        "captcha_events": payload.captchaEvents or [],
        "created_at": int(time.time())
    }

    if mongo_db is not None:
        mongo_db["captcha_attempts"].insert_one(attempt_doc)

    return {
        "ok": True,
        "success": success,
        "message": "CAPTCHA passed" if success else "Incorrect selection"
    }


@app.get("/login")
def redirect_login():
    return RedirectResponse(url="/", status_code=302)


@app.get("/register")
def redirect_register():
    return RedirectResponse(url="/", status_code=302)


@app.get("/checkout")
def redirect_checkout():
    return RedirectResponse(url="/", status_code=302)


app.mount("/", StaticFiles(directory=str(ROOT / "public"), html=True), name="public")