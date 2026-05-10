(function (global) {
  "use strict";

  const DEFAULTS = {
    endpoint: "/api/risk-score",
    maxEvents: 500,
    autoStart: true,
    debug: false
  };

  let config = { ...DEFAULTS };
  let started = false;
  let startedAt = 0;
  let events = [];
  let sessionId = null;
  let lastAssessment = null;

  function log(...args) {
    if (config.debug) {
      console.log("[BehaviorCaptcha]", ...args);
    }
  }

  function generateSessionId() {
    return "sess_" + Math.random().toString(36).slice(2) + "_" + Date.now().toString(36);
  }

  function nowOffset() {
    return Date.now() - startedAt;
  }

  function safeTargetName(target) {
    if (!target) return "";
    if (target.id) return target.id;
    if (target.name) return target.name;
    if (target.tagName) return String(target.tagName).toLowerCase();
    return "";
  }

  function trimEvents() {
    if (events.length > config.maxEvents) {
      events = events.slice(events.length - config.maxEvents);
    }
  }

  function pushEvent(type, data = {}) {
    if (!started) return;

    events.push({
      type,
      t: nowOffset(),
      ...data
    });

    trimEvents();
  }

  function onMouseMove(e) {
    pushEvent("mousemove", {
      x: e.clientX,
      y: e.clientY,
      target: safeTargetName(e.target)
    });
  }

  function onClick(e) {
    pushEvent("click", {
      x: e.clientX,
      y: e.clientY,
      target: safeTargetName(e.target)
    });
  }

  function onKeyDown(e) {
    pushEvent("keydown", {
      key: e.key,
      target: safeTargetName(e.target)
    });
  }

  function onScroll() {
    pushEvent("scroll", {
      scrollY: global.scrollY || global.pageYOffset || 0
    });
  }

  function onFocus() {
    pushEvent("focus");
  }

  function onBlur() {
    pushEvent("blur");
  }

  function addListeners() {
    global.addEventListener("mousemove", onMouseMove, { passive: true });
    global.addEventListener("click", onClick, { passive: true });
    global.addEventListener("keydown", onKeyDown, { passive: true });
    global.addEventListener("scroll", onScroll, { passive: true });
    global.addEventListener("focus", onFocus);
    global.addEventListener("blur", onBlur);
  }

  function removeListeners() {
    global.removeEventListener("mousemove", onMouseMove);
    global.removeEventListener("click", onClick);
    global.removeEventListener("keydown", onKeyDown);
    global.removeEventListener("scroll", onScroll);
    global.removeEventListener("focus", onFocus);
    global.removeEventListener("blur", onBlur);
  }

  function buildMeta() {
    return {
      userAgent: navigator.userAgent || "",
      screenWidth: global.screen?.width || 0,
      screenHeight: global.screen?.height || 0,
      viewportWidth: global.innerWidth || 0,
      viewportHeight: global.innerHeight || 0
    };
  }

  function init(userConfig = {}) {
    config = { ...DEFAULTS, ...userConfig };

    if (config.autoStart) {
      startBackgroundMonitoring();
    }

    return api;
  }

  function startBackgroundMonitoring() {
    if (started) return;

    started = true;
    startedAt = Date.now();
    sessionId = generateSessionId();
    events = [];
    lastAssessment = null;

    addListeners();
    log("started", sessionId);
  }

  function stopBackgroundMonitoring() {
    if (!started) return;

    removeListeners();
    started = false;
    log("stopped");
  }

  function clearEvents() {
    events = [];
  }

  function reset() {
    stopBackgroundMonitoring();
    clearEvents();
    startBackgroundMonitoring();
  }

  function getEvents() {
    return [...events];
  }

  function getSessionId() {
    return sessionId;
  }

  function getLastAssessment() {
    return lastAssessment;
  }

  async function evaluate() {
    if (!started) {
      throw new Error("BehaviorCaptcha is not started");
    }

    const response = await fetch(config.endpoint, {
      method: "POST",
      headers: {
        "Content-Type": "application/json"
      },
      body: JSON.stringify({
        sessionId,
        events,
        meta: buildMeta()
      })
    });

    if (!response.ok) {
      throw new Error(`HTTP ${response.status}`);
    }

    const data = await response.json();
    lastAssessment = data;
    return data;
  }

  async function requireChallenge() {
    const result = await evaluate();
    return result.decision !== "allow";
  }

  const api = {
    init,
    startBackgroundMonitoring,
    stopBackgroundMonitoring,
    clearEvents,
    reset,
    getEvents,
    getSessionId,
    getLastAssessment,
    evaluate,
    requireChallenge
  };

  global.BehaviorCaptcha = api;
})(window);