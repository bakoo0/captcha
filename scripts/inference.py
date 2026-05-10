import argparse
import json
import math
import os
import statistics

import joblib
import numpy as np


def safe_mean(values):
    vals = [float(v) for v in values if v is not None]
    if not vals:
        return 0.0
    return float(sum(vals) / len(vals))


def safe_std(values):
    vals = [float(v) for v in values if v is not None]
    if len(vals) < 2:
        return 0.0
    return float(statistics.pstdev(vals))


def safe_max(values):
    vals = [float(v) for v in values if v is not None]
    if not vals:
        return 0.0
    return float(max(vals))


def clamp(x, lo, hi):
    return max(lo, min(hi, x))


def extract_features(events):
    safe_events = events if isinstance(events, list) else []
    safe_events = [e for e in safe_events if isinstance(e, dict)]

    n_events = len(safe_events)

    times = []
    mousemove_n = 0
    mousedown_n = 0
    mouseup_n = 0
    click_n = 0
    scroll_event_n = 0
    keydown_n = 0
    keyup_n = 0
    focus_n = 0
    blur_n = 0

    mouse_points = []
    scroll_values = []
    key_times = []
    keys = []
    backspace_n = 0

    focus_jump_total = 0
    prev_focus_target = None

    for e in safe_events:
        etype = str(e.get("type", "")).lower()
        t = e.get("t", 0)

        try:
            t = float(t)
        except Exception:
            t = 0.0

        times.append(t)

        if etype == "mousemove":
            mousemove_n += 1
            x = e.get("x")
            y = e.get("y")
            try:
                x = float(x)
                y = float(y)
                mouse_points.append((t, x, y))
            except Exception:
                pass

        elif etype == "mousedown":
            mousedown_n += 1

        elif etype == "mouseup":
            mouseup_n += 1

        elif etype == "click":
            click_n += 1

        elif etype == "scroll":
            scroll_event_n += 1
            sv = e.get("scrollY", 0)
            try:
                scroll_values.append(float(sv))
            except Exception:
                scroll_values.append(0.0)

        elif etype == "keydown":
            keydown_n += 1
            key_times.append(t)
            k = str(e.get("key", "") or "")
            keys.append(k)
            if k.lower() == "backspace":
                backspace_n += 1

        elif etype == "keyup":
            keyup_n += 1

        elif etype == "focus":
            focus_n += 1
            current_target = str(e.get("target", "") or "")
            if prev_focus_target is not None and current_target and current_target != prev_focus_target:
                focus_jump_total += 1
            if current_target:
                prev_focus_target = current_target

        elif etype == "blur":
            blur_n += 1

    session_start_ms = min(times) if times else 0.0
    session_end_ms = max(times) if times else 0.0
    duration_ms = max(0.0, session_end_ms - session_start_ms)
    duration_sec = duration_ms / 1000.0 if duration_ms > 0 else 0.0

    events_per_sec = n_events / duration_sec if duration_sec > 0 else 0.0
    clicks_per_sec = click_n / duration_sec if duration_sec > 0 else 0.0
    keys_per_sec = keydown_n / duration_sec if duration_sec > 0 else 0.0
    scrolls_per_sec = scroll_event_n / duration_sec if duration_sec > 0 else 0.0

    mouse_n = len(mouse_points)
    mouse_path_len = 0.0
    mouse_displacement = 0.0
    mouse_straightness = 0.0
    mouse_speeds = []
    mouse_dts = []
    mouse_direction_changes = 0
    mouse_idle_pauses = 0

    prev_angle = None

    if mouse_n >= 2:
        x0, y0 = mouse_points[0][1], mouse_points[0][2]
        x1, y1 = mouse_points[-1][1], mouse_points[-1][2]
        mouse_displacement = math.sqrt((x1 - x0) ** 2 + (y1 - y0) ** 2)

        for i in range(1, mouse_n):
            t_prev, x_prev, y_prev = mouse_points[i - 1]
            t_cur, x_cur, y_cur = mouse_points[i]

            dx = x_cur - x_prev
            dy = y_cur - y_prev
            dt = t_cur - t_prev

            dist = math.sqrt(dx * dx + dy * dy)
            mouse_path_len += dist

            if dt > 0:
                mouse_dts.append(dt)
                mouse_speeds.append(dist / dt)

            if dt > 1000:
                mouse_idle_pauses += 1

            if dist > 0:
                angle = math.atan2(dy, dx)
                if prev_angle is not None:
                    diff = angle - prev_angle
                    while diff > math.pi:
                        diff -= 2 * math.pi
                    while diff < -math.pi:
                        diff += 2 * math.pi
                    if abs(diff) > 0.6:
                        mouse_direction_changes += 1
                prev_angle = angle

        if mouse_path_len > 0:
            mouse_straightness = mouse_displacement / mouse_path_len

    scroll_n = len(scroll_values)
    scroll_deltas = []
    scroll_bursts = 0

    if scroll_n >= 2:
        for i in range(1, scroll_n):
            delta = scroll_values[i] - scroll_values[i - 1]
            scroll_deltas.append(delta)

        current_burst = 1
        for i in range(1, len(scroll_values)):
            if abs(scroll_values[i] - scroll_values[i - 1]) > 0:
                current_burst += 1
            else:
                if current_burst >= 3:
                    scroll_bursts += 1
                current_burst = 1
        if current_burst >= 3:
            scroll_bursts += 1

    key_n = len(key_times)
    interkeys = []
    if key_n >= 2:
        for i in range(1, key_n):
            interkeys.append(key_times[i] - key_times[i - 1])

    unique_keys = len(set(keys))

    features = {
        "n_events": float(n_events),
        "session_start_ms": float(session_start_ms),
        "session_end_ms": float(session_end_ms),
        "duration_ms": float(duration_ms),
        "mousemove_n": float(mousemove_n),
        "mousedown_n": float(mousedown_n),
        "mouseup_n": float(mouseup_n),
        "click_n": float(click_n),
        "scroll_event_n": float(scroll_event_n),
        "keydown_n": float(keydown_n),
        "keyup_n": float(keyup_n),
        "events_per_sec": float(events_per_sec),
        "clicks_per_sec": float(clicks_per_sec),
        "keys_per_sec": float(keys_per_sec),
        "scrolls_per_sec": float(scrolls_per_sec),
        "mouse_n": float(mouse_n),
        "mouse_path_len": float(mouse_path_len),
        "mouse_displacement": float(mouse_displacement),
        "mouse_straightness": float(mouse_straightness),
        "mouse_speed_mean": float(safe_mean(mouse_speeds)),
        "mouse_speed_std": float(safe_std(mouse_speeds)),
        "mouse_speed_max": float(safe_max(mouse_speeds)),
        "mouse_move_dt_mean": float(safe_mean(mouse_dts)),
        "mouse_move_dt_std": float(safe_std(mouse_dts)),
        "mouse_direction_changes": float(mouse_direction_changes),
        "mouse_idle_pauses": float(mouse_idle_pauses),
        "scroll_n": float(scroll_n),
        "scroll_delta_mean": float(safe_mean(scroll_deltas)),
        "scroll_delta_std": float(safe_std(scroll_deltas)),
        "scroll_delta_max": float(safe_max([abs(v) for v in scroll_deltas])),
        "scroll_bursts": float(scroll_bursts),
        "key_n": float(key_n),
        "interkey_mean": float(safe_mean(interkeys)),
        "interkey_std": float(safe_std(interkeys)),
        "backspace_n": float(backspace_n),
        "unique_keys": float(unique_keys),
        "focus_n": float(focus_n),
        "blur_n": float(blur_n),
        "focus_jump_total": float(focus_jump_total),
    }

    return features


def fallback_decision(prob):
    prob = clamp(float(prob), 0.0, 1.0)
    if prob <= 0.3:
        return "allow"
    if prob <= 0.7:
        return "show_captcha"
    return "hard_captcha"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    with open(args.input, "r", encoding="utf-8") as f:
        payload = json.load(f)

    events = payload.get("events", [])
    features = extract_features(events)

    bundle_path = os.path.join(os.path.dirname(__file__), "bot_detector_bundle.joblib")
    bundle = joblib.load(bundle_path)

    model = bundle["model"]
    feature_cols = bundle["feature_cols"]
    thresholds = bundle.get("thresholds", {"allow_max": 0.3, "captcha_max": 0.7})
    model_name = bundle.get("model_name", "RandomForest")

    vector = np.array([[features.get(col, 0.0) for col in feature_cols]], dtype=float)

    if hasattr(model, "predict_proba"):
        proba = model.predict_proba(vector)[0]
        if len(proba) == 2:
            bot_probability = float(proba[1])
        else:
            bot_probability = float(max(proba))
    else:
        bot_probability = float(model.predict(vector)[0])

    bot_probability = clamp(bot_probability, 0.0, 1.0)

    allow_max = float(thresholds.get("allow_max", 0.3))
    captcha_max = float(thresholds.get("captcha_max", 0.7))

    if bot_probability <= allow_max:
        decision = "allow"
    elif bot_probability <= captcha_max:
        decision = "show_captcha"
    else:
        decision = "hard_captcha"

    result = {
        "score": round(bot_probability, 6),
        "decision": decision,
        "model_source": model_name,
        "thresholds": {
            "allow_max": allow_max,
            "captcha_max": captcha_max
        },
        "features": features
    }

    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    main()