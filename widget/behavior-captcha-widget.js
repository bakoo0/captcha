(function (window, document) {
  "use strict";

  const DEFAULTS = {
    endpoint: window.location.origin,
    siteKey: "demo-site",
    maxEvents: 700,
    mousemoveThrottleMs: 35,
    autoStart: true,
    debug: false
  };

  let config = { ...DEFAULTS };
  let started = false;
  let startedAt = 0;
  let sessionId = null;
  let events = [];
  let captchaEvents = [];
  let lastRiskResult = null;
  let currentChallenge = null;
  let lastMouseMoveAt = 0;

  function log(...args) {
    if (config.debug) console.log("[BehaviorCaptcha]", ...args);
  }

  function scriptDatasetConfig() {
    const script = document.currentScript;
    if (!script) return {};
    const out = {};
    if (script.dataset.endpoint) out.endpoint = script.dataset.endpoint.replace(/\/$/, "");
    if (script.dataset.siteKey) out.siteKey = script.dataset.siteKey;
    if (script.dataset.debug) out.debug = script.dataset.debug === "true";
    if (script.dataset.autoStart) out.autoStart = script.dataset.autoStart !== "false";
    return out;
  }

  function generateSessionId() {
    return "sess_" + Math.random().toString(36).slice(2) + "_" + Date.now().toString(36);
  }

  function nowOffset() {
    return Date.now() - startedAt;
  }

  function safeTargetName(target) {
    if (!target) return "";
    if (target.id) return "#" + target.id;
    if (target.name) return "[name='" + target.name + "']";
    if (target.className && typeof target.className === "string") {
      return target.tagName.toLowerCase() + "." + target.className.split(" ").filter(Boolean).slice(0, 2).join(".");
    }
    return target.tagName ? target.tagName.toLowerCase() : "";
  }

  function normalizeKey(key) {
    if (!key) return "";
    const allowed = ["Backspace", "Enter", "Tab", "Shift", "Control", "Alt", "Escape", "ArrowUp", "ArrowDown", "ArrowLeft", "ArrowRight"];
    if (allowed.includes(key)) return key;
    return "char";
  }

  function trimEvents() {
    if (events.length > config.maxEvents) {
      events = events.slice(events.length - config.maxEvents);
    }
  }

  function pushEvent(type, data = {}) {
    if (!started) return;
    const event = { type, t: nowOffset(), ...data };
    events.push(event);
    if (String(type).startsWith("captcha_")) captchaEvents.push(event);
    trimEvents();
  }

  function onMouseMove(e) {
    const now = Date.now();
    if (now - lastMouseMoveAt < config.mousemoveThrottleMs) return;
    lastMouseMoveAt = now;
    pushEvent("mousemove", { x: e.clientX, y: e.clientY, target: safeTargetName(e.target) });
  }

  function onMouseDown(e) {
    pushEvent("mousedown", { x: e.clientX, y: e.clientY, target: safeTargetName(e.target) });
  }

  function onMouseUp(e) {
    pushEvent("mouseup", { x: e.clientX, y: e.clientY, target: safeTargetName(e.target) });
  }

  function onClick(e) {
    pushEvent("click", { x: e.clientX, y: e.clientY, target: safeTargetName(e.target) });
  }

  function onKeyDown(e) {
    pushEvent("keydown", { key: normalizeKey(e.key), target: safeTargetName(e.target) });
  }

  function onKeyUp(e) {
    pushEvent("keyup", { key: normalizeKey(e.key), target: safeTargetName(e.target) });
  }

  function onScroll() {
    pushEvent("scroll", { scrollY: window.scrollY || window.pageYOffset || 0 });
  }

  function onFocusIn(e) {
    pushEvent("focus", { target: safeTargetName(e.target) });
  }

  function onFocusOut(e) {
    pushEvent("blur", { target: safeTargetName(e.target) });
  }

  function addListeners() {
    window.addEventListener("mousemove", onMouseMove, { passive: true });
    window.addEventListener("mousedown", onMouseDown, { passive: true });
    window.addEventListener("mouseup", onMouseUp, { passive: true });
    window.addEventListener("click", onClick, { passive: true });
    window.addEventListener("keydown", onKeyDown, { passive: true });
    window.addEventListener("keyup", onKeyUp, { passive: true });
    window.addEventListener("scroll", onScroll, { passive: true });
    document.addEventListener("focusin", onFocusIn, true);
    document.addEventListener("focusout", onFocusOut, true);
  }

  function removeListeners() {
    window.removeEventListener("mousemove", onMouseMove);
    window.removeEventListener("mousedown", onMouseDown);
    window.removeEventListener("mouseup", onMouseUp);
    window.removeEventListener("click", onClick);
    window.removeEventListener("keydown", onKeyDown);
    window.removeEventListener("keyup", onKeyUp);
    window.removeEventListener("scroll", onScroll);
    document.removeEventListener("focusin", onFocusIn, true);
    document.removeEventListener("focusout", onFocusOut, true);
  }

  function buildMeta() {
    return {
      userAgent: navigator.userAgent || "",
      language: navigator.language || "",
      screenWidth: window.screen?.width || 0,
      screenHeight: window.screen?.height || 0,
      viewportWidth: window.innerWidth || 0,
      viewportHeight: window.innerHeight || 0,
      timezone: Intl.DateTimeFormat().resolvedOptions().timeZone || ""
    };
  }


  function injectStyles() {
    if (document.getElementById("behavior-captcha-widget-styles")) return;
    const style = document.createElement("style");
    style.id = "behavior-captcha-widget-styles";
    style.textContent = `
      .bcaptcha-box{margin-top:18px;padding:18px;border:1px solid #d1d5db;border-radius:18px;background:#fff;box-shadow:0 14px 35px rgba(15,23,42,.10);font-family:Inter,Arial,sans-serif;color:#111827}
      .bcaptcha-title{font-size:18px;font-weight:800;margin-bottom:6px}
      .bcaptcha-instruction{margin:0 0 14px;color:#4b5563;line-height:1.5}
      .bcaptcha-grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:12px}
      .bcaptcha-item{border:2px solid transparent;border-radius:16px;overflow:hidden;background:#fff;padding:0;cursor:pointer;transition:.18s ease;box-shadow:0 4px 12px rgba(15,23,42,.06)}
      .bcaptcha-item:hover{transform:translateY(-2px);box-shadow:0 10px 20px rgba(15,23,42,.12)}
      .bcaptcha-item.selected{border-color:#2563eb;box-shadow:0 0 0 4px rgba(37,99,235,.14)}
      .bcaptcha-item img{width:100%;height:145px;display:block;object-fit:cover}
      .bcaptcha-footer{display:flex;gap:10px;align-items:center;margin-top:14px}
      .bcaptcha-verify{border:0;border-radius:12px;background:#111827;color:#fff;padding:11px 16px;font-weight:800;cursor:pointer}
      .bcaptcha-verify:disabled{opacity:.6;cursor:not-allowed}
      .bcaptcha-result{margin-top:12px;font-weight:800;color:#374151}
      .bcaptcha-result.success{color:#166534}
      .bcaptcha-result.error{color:#991b1b}
      @media(max-width:720px){.bcaptcha-grid{grid-template-columns:repeat(2,minmax(0,1fr))}.bcaptcha-item img{height:125px}}
    `;
    document.head.appendChild(style);
  }

  function init(userConfig = {}) {
    injectStyles();
    config = { ...DEFAULTS, ...scriptDatasetConfig(), ...userConfig };
    config.endpoint = String(config.endpoint || window.location.origin).replace(/\/$/, "");
    if (config.autoStart) start();
    return api;
  }

  function start() {
    if (started) return;
    started = true;
    startedAt = Date.now();
    sessionId = generateSessionId();
    events = [];
    captchaEvents = [];
    currentChallenge = null;
    lastRiskResult = null;
    addListeners();
    log("started", sessionId);
  }

  function stop() {
    if (!started) return;
    removeListeners();
    started = false;
    log("stopped", sessionId);
  }

  function reset() {
    stop();
    start();
  }

  async function evaluate() {
    if (!started) start();
    const response = await fetch(config.endpoint + "/api/risk-score", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        sessionId,
        siteKey: config.siteKey,
        events,
        meta: buildMeta()
      })
    });
    if (!response.ok) throw new Error("Risk API failed: HTTP " + response.status);
    const data = await response.json();
    lastRiskResult = data;
    return data;
  }

  async function flushEvents() {
    if (!started) start();
    const response = await fetch(config.endpoint + "/api/events", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        sessionId,
        siteKey: config.siteKey,
        events,
        meta: buildMeta()
      })
    });
    if (!response.ok) throw new Error("Events API failed: HTTP " + response.status);
    return await response.json();
  }

  async function loadCaptcha(level) {
    if (!started) start();
    const url = config.endpoint + "/api/captcha/challenge?sessionId=" + encodeURIComponent(sessionId) + "&level=" + encodeURIComponent(level || "medium");
    const response = await fetch(url);
    if (!response.ok) throw new Error("CAPTCHA challenge API failed: HTTP " + response.status);
    currentChallenge = await response.json();
    return currentChallenge;
  }

  async function verifyCaptcha(selectedIds) {
    if (!currentChallenge) throw new Error("No active CAPTCHA challenge");
    const response = await fetch(config.endpoint + "/api/captcha/verify", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        sessionId,
        challengeId: currentChallenge.challengeId,
        selectedIds,
        captchaEvents
      })
    });
    if (!response.ok) throw new Error("CAPTCHA verify API failed: HTTP " + response.status);
    return await response.json();
  }

  function renderCaptcha(container, challenge) {
    if (typeof container === "string") container = document.querySelector(container);
    if (!container) throw new Error("CAPTCHA container not found");

    container.innerHTML = "";
    const selected = new Set();

    const box = document.createElement("div");
    box.className = "bcaptcha-box";

    const title = document.createElement("div");
    title.className = "bcaptcha-title";
    title.textContent = challenge.level === "hard" ? "Advanced Pareidolia CAPTCHA" : "Image CAPTCHA";

    const instruction = document.createElement("p");
    instruction.className = "bcaptcha-instruction";
    instruction.textContent = challenge.instruction || "Select the required images.";

    const grid = document.createElement("div");
    grid.className = "bcaptcha-grid";

    challenge.items.forEach((item) => {
      const btn = document.createElement("button");
      btn.type = "button";
      btn.className = "bcaptcha-item";
      btn.dataset.id = item.id;

      const img = document.createElement("img");
      img.src = item.src.startsWith("http") ? item.src : config.endpoint + item.src;
      img.alt = item.alt || "captcha image";
      btn.appendChild(img);

      btn.addEventListener("click", () => {
        pushEvent("captcha_click", { imageId: item.id, target: "captcha-image" });
        if (selected.has(item.id)) {
          selected.delete(item.id);
          btn.classList.remove("selected");
        } else {
          selected.add(item.id);
          btn.classList.add("selected");
        }
      });
      grid.appendChild(btn);
    });

    const footer = document.createElement("div");
    footer.className = "bcaptcha-footer";

    const verify = document.createElement("button");
    verify.type = "button";
    verify.className = "bcaptcha-verify";
    verify.textContent = "Verify";

    const result = document.createElement("div");
    result.className = "bcaptcha-result";

    verify.addEventListener("click", async () => {
      verify.disabled = true;
      result.textContent = "Checking...";
      try {
        const data = await verifyCaptcha(Array.from(selected));
        if (data.success) {
          result.textContent = "Verified successfully.";
          result.className = "bcaptcha-result success";
          window.dispatchEvent(new CustomEvent("behaviorcaptcha:verified", { detail: data }));
        } else {
          result.textContent = "Incorrect selection. Try again.";
          result.className = "bcaptcha-result error";
          verify.disabled = false;
        }
      } catch (error) {
        result.textContent = String(error.message || error);
        result.className = "bcaptcha-result error";
        verify.disabled = false;
      }
    });

    footer.appendChild(verify);
    box.appendChild(title);
    box.appendChild(instruction);
    box.appendChild(grid);
    box.appendChild(footer);
    box.appendChild(result);
    container.appendChild(box);
  }

  async function runAdaptiveCheck(containerSelector) {
    const result = await evaluate();
    const container = typeof containerSelector === "string" ? document.querySelector(containerSelector) : containerSelector;
    if (result.decision === "allow") return { status: "allowed", risk: result };
    const level = result.decision === "hard_captcha" ? "hard" : "medium";
    const challenge = await loadCaptcha(level);
    if (container) renderCaptcha(container, challenge);
    return { status: "captcha_required", risk: result, challenge };
  }

  async function protectForm(formSelector, options = {}) {
    const form = typeof formSelector === "string" ? document.querySelector(formSelector) : formSelector;
    if (!form) throw new Error("Form not found");
    const captchaContainer = document.querySelector(options.captchaContainer || "#behavior-captcha-container");

    form.addEventListener("submit", async (e) => {
      if (form.dataset.behaviorVerified === "true") return;
      e.preventDefault();
      const result = await runAdaptiveCheck(captchaContainer);
      if (result.status === "allowed") {
        form.dataset.behaviorVerified = "true";
        if (options.submitAfterAllow !== false) form.submit();
      }
    });
  }

  const api = {
    init,
    start,
    stop,
    reset,
    evaluate,
    flushEvents,
    loadCaptcha,
    verifyCaptcha,
    renderCaptcha,
    runAdaptiveCheck,
    protectForm,
    pushEvent,
    getSessionId: () => sessionId,
    getEvents: () => [...events],
    getLastRiskResult: () => lastRiskResult
  };

  window.BehaviorCaptcha = api;
  init();
})(window, document);
