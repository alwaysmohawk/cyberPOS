#!/usr/bin/env python3
"""
cyberPOS NAGGER
Runs forever (systemd: cyberpos-nagger.service), waking once a minute to send push nags:
  - focus timer finished
  - "your one thing" when nothing has been started or finished for a while
  - daily overdue-chores reminder
  - system alerts: a dispatch receipt failed, or Google got disconnected
Everything obeys the toggles in the console's Settings; the master switch silences all but
system alerts (which have their own toggle). Quiet hours silence everything except timers.
"""

import time
import traceback
from datetime import datetime, timedelta

import store
import push
import picker
import receipts
from google_tasks_helper import list_all_tasks, token_status

TICK_SECONDS = 60


def on(key):
    return store.get_setting(key, "0") == "1"


def hhmm(value, default):
    try:
        h, m = (int(x) for x in value.split(":"))
        return h * 60 + m
    except (ValueError, AttributeError):
        return default


def in_quiet_hours(now):
    start = hhmm(store.get_setting("quiet_start"), 22 * 60 + 30)
    end = hhmm(store.get_setting("quiet_end"), 9 * 60)
    minute = now.hour * 60 + now.minute
    if start <= end:
        return start <= minute < end
    return minute >= start or minute < end  # wraps midnight


def task_path(t):
    return f"/api/task/{t['list_id']}/{t['id']}"


def check_timer(now):
    timer = store.get_timer()
    if not timer or timer["notified"] or not on("nag_timer"):
        return
    if datetime.fromisoformat(timer["ends_at"]) > now:
        return
    path = None
    try:
        t = next((t for t in list_all_tasks() if t["id"] == timer["task_id"]), None)
        path = task_path(t) if t else None
    except Exception:
        pass
    actions = [{"action": "more", "title": "+10 min"}]
    if path:
        actions.insert(0, {"action": "done", "title": "✓ Done"})
    push.send("⏰ Time's up", f"{timer['title']}. Done, or 10 more minutes?", url="/",
              tag="timer", actions=actions, data={"task_path": path})
    store.mark_timer_notified()


def check_focus(now):
    if not on("nag_focus") or store.get_timer():
        return
    every = timedelta(minutes=int(store.get_setting("nag_focus_every_min", "120") or 120))
    last_activity = store.last_event_ts(("task", "chore", "timer_start"))
    last_nag, _ = store.nag_last("focus")
    quiet_end = hhmm(store.get_setting("quiet_end"), 9 * 60)
    day_start = now.replace(hour=quiet_end // 60, minute=quiet_end % 60, second=0, microsecond=0)
    # The clock starts at the end of quiet hours, so the first nag comes `every` after waking
    baseline = max(x for x in (last_activity, last_nag, day_start) if x is not None)
    if now - baseline < every:
        return
    try:
        ranked = picker.ranked(score_missing=False)
    except Exception as e:
        print(f"focus nag: couldn't load tasks ({e})")
        return
    pinned = store.get_setting("focus_task_id")
    top = next((t for t in ranked if t["id"] == pinned), ranked[0] if ranked else None)
    if not top:
        return
    label = picker.due_label(top["due"])
    body = top["title"] + (f"  ·  {label}" if label else "")
    push.send("◉ Your one thing", body, url="/", tag="focus",
              actions=[{"action": "start", "title": "▶ Start 10 min"}, {"action": "done", "title": "✓ Done"}],
              data={"task_path": task_path(top)})
    store.nag_mark("focus", top["id"])


def check_chores(now):
    if not on("nag_chores"):
        return
    if now.hour * 60 + now.minute < hhmm(store.get_setting("nag_chores_at"), 18 * 60):
        return
    last, _ = store.nag_last("chores")
    if last and last.date() == now.date():
        return
    overdue = store.overdue_chores()
    store.nag_mark("chores")
    if not overdue:
        return
    top = overdue[0]
    more = f" (+{len(overdue) - 1} more)" if len(overdue) > 1 else ""
    push.send("⌂ Home check", f"{top['title']}: {top['days_since']} days{more}. Ten minutes?", url="/chores", tag="chores")


def check_alerts(now):
    if not on("nag_alerts"):
        return
    for name, st in receipts.dispatch_status().items():
        kind = f"alert_{name}"
        last, ref = store.nag_last(kind)
        if st["result"] in ("success", "unknown") or not st["invocation"]:
            continue
        if last is None:
            store.nag_mark(kind, st["invocation"])  # first run: don't alert about old failures
            continue
        if ref != st["invocation"]:
            push.send("⚠ Receipt failed", f"The {name} dispatch didn't print ({st['result']}). Tap for details.",
                      url="/print", tag=kind)
            store.nag_mark(kind, st["invocation"])

    last, _ = store.nag_last("google_check")
    if last and now - last < timedelta(minutes=30):
        return
    store.nag_mark("google_check")
    status, detail = token_status()
    if status == "ok":
        return
    last_alert, _ = store.nag_last("alert_google")
    if last_alert and now - last_alert < timedelta(hours=12):
        return
    push.send("⚠ Google disconnected", "Receipts and tasks are offline. Tap to reconnect.", url="/settings", tag="google")
    store.nag_mark("alert_google")


def tick():
    now = store.now()
    quiet = in_quiet_hours(now)
    if on("nag_enabled"):
        check_timer(now)  # a timer you started still rings in quiet hours
        if not quiet:
            check_focus(now)
            check_chores(now)
    if not quiet:
        check_alerts(now)


def main():
    store.init()
    print("cyberPOS nagger online")
    while True:
        try:
            if store.push_subs():
                tick()
        except Exception:
            traceback.print_exc()
        time.sleep(TICK_SECONDS)


if __name__ == "__main__":
    main()
