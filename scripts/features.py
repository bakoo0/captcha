import math
from collections import Counter

def safe_div(a, b):
    return a / b if b not in (0, None) else 0.0

def extract_session_features(events):
    if not events:
        return {
            "n_events": 0,
            "duration_ms": 0,
            "mousemove_n": 0,
            "mousedown_n": 0,
            "mouseup_n": 0,
            "click_n": 0,
            "scroll_event_n": 0,
            "keydown_n": 0,
            "keyup_n": 0,
            "focus_n": 0,
            "blur_n": 0,
            "events_per_sec": 0,
            "clicks_per_sec": 0,
            "keys_per_sec": 0,
            "scrolls_per_sec": 0,
            "mouse_path_len": 0,
            "mouse_displacement": 0,
            "mouse_straightness": 0,
            "mouse_speed_mean": 0,
            "mouse_speed_max": 0,
            "mouse_direction_changes": 0,
            "mouse_idle_pauses": 0,
            "scroll_delta_mean": 0,
            "scroll_delta_max": 0,
            "scroll_bursts": 0,
            "interkey_mean": 0,
            "backspace_n": 0,
            "unique_keys": 0,
            "focus_jump_total": 0,
        }

    events = sorted(events, key=lambda x: x.get("t_ms", 0))

    types = [e.get("eventType", "") for e in events]
    c = Counter(types)

    t0 = events[0].get("t_ms", 0)
    t1 = events[-1].get("t_ms", 0)
    duration_ms = max(0, t1 - t0)
    duration_sec = duration_ms / 1000 if duration_ms > 0 else 0

    mouse_events = [e for e in events if e.get("eventType") == "mousemove"]
    keydown_events = [e for e in events if e.get("eventType") == "keydown"]
    scroll_events = [e for e in events if e.get("eventType") == "scroll"]

    mouse_path_len = 0.0
    mouse_speeds = []
    direction_changes = 0
    idle_pauses = 0

    prev_dx = None
    prev_dy = None

    for i in range(1, len(mouse_events)):
      a = mouse_events[i - 1]
      b = mouse_events[i]

      dx = (b.get("pageX", 0) or 0) - (a.get("pageX", 0) or 0)
      dy = (b.get("pageY", 0) or 0) - (a.get("pageY", 0) or 0)
      dt = (b.get("t_ms", 0) or 0) - (a.get("t_ms", 0) or 0)

      dist = math.sqrt(dx * dx + dy * dy)
      mouse_path_len += dist

      if dt > 0:
          mouse_speeds.append(dist / dt)

      if dt > 1000:
          idle_pauses += 1

      if prev_dx is not None and prev_dy is not None:
          if (dx * prev_dx + dy * prev_dy) < 0:
              direction_changes += 1

      prev_dx, prev_dy = dx, dy

    if len(mouse_events) >= 2:
        start = mouse_events[0]
        end = mouse_events[-1]
        mx = (end.get("pageX", 0) or 0) - (start.get("pageX", 0) or 0)
        my = (end.get("pageY", 0) or 0) - (start.get("pageY", 0) or 0)
        mouse_displacement = math.sqrt(mx * mx + my * my)
    else:
        mouse_displacement = 0.0

    mouse_straightness = safe_div(mouse_displacement, mouse_path_len)

    scroll_deltas = [abs(e.get("deltaY", 0) or 0) for e in scroll_events]
    scroll_delta_mean = sum(scroll_deltas) / len(scroll_deltas) if scroll_deltas else 0
    scroll_delta_max = max(scroll_deltas) if scroll_deltas else 0
    scroll_bursts = sum(1 for d in scroll_deltas if d > 200)

    key_times = [e.get("t_ms", 0) for e in keydown_events]
    interkeys = [key_times[i] - key_times[i - 1] for i in range(1, len(key_times))]
    interkey_mean = sum(interkeys) / len(interkeys) if interkeys else 0

    pressed_keys = [str(e.get("key", "")) for e in keydown_events]
    backspace_n = sum(1 for k in pressed_keys if k.lower() == "backspace")
    unique_keys = len(set(pressed_keys)) if pressed_keys else 0

    return {
        "n_events": len(events),
        "duration_ms": duration_ms,

        "mousemove_n": c.get("mousemove", 0),
        "mousedown_n": c.get("mousedown", 0),
        "mouseup_n": c.get("mouseup", 0),
        "click_n": c.get("click", 0),
        "scroll_event_n": c.get("scroll", 0),
        "keydown_n": c.get("keydown", 0),
        "keyup_n": c.get("keyup", 0),
        "focus_n": c.get("focus", 0),
        "blur_n": c.get("blur", 0),

        "events_per_sec": safe_div(len(events), duration_sec),
        "clicks_per_sec": safe_div(c.get("click", 0), duration_sec),
        "keys_per_sec": safe_div(c.get("keydown", 0), duration_sec),
        "scrolls_per_sec": safe_div(c.get("scroll", 0), duration_sec),

        "mouse_path_len": mouse_path_len,
        "mouse_displacement": mouse_displacement,
        "mouse_straightness": mouse_straightness,
        "mouse_speed_mean": sum(mouse_speeds) / len(mouse_speeds) if mouse_speeds else 0,
        "mouse_speed_max": max(mouse_speeds) if mouse_speeds else 0,
        "mouse_direction_changes": direction_changes,
        "mouse_idle_pauses": idle_pauses,

        "scroll_delta_mean": scroll_delta_mean,
        "scroll_delta_max": scroll_delta_max,
        "scroll_bursts": scroll_bursts,

        "interkey_mean": interkey_mean,
        "backspace_n": backspace_n,
        "unique_keys": unique_keys,

        "focus_jump_total": c.get("focus", 0) + c.get("blur", 0),
    }