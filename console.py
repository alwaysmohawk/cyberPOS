#!/usr/bin/env python3
"""
cyberPOS CONSOLE
Phone-first web app for the thermal task node: one-thing focus screen, quick capture,
task board, chores, routines, wins log, print panel and settings.
Replaces task_server.py on port 5000; /complete/<list>/<task> QR links keep working.

Run (production): gunicorn -w 1 --threads 8 -b 0.0.0.0:5000 console:app
Run (dev):        python3 console.py
"""

import json
import logging
import threading
import time
from datetime import date, datetime, timedelta

from flask import Flask, abort, jsonify, redirect, render_template, request

import store
import picker
import receipts
from google_tasks_helper import (
    complete_task, create_task, update_task, get_task_lists, list_all_tasks,
    estimate_difficulty_and_minutes, token_status, reauth_start, reauth_finish,
)

app = Flask(__name__)
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("console")

store.init()

ROUTINES = ["morning", "evening", "night"]


# ===== GOOGLE TASKS CACHE =====
# Listing every list costs a few API calls, so pages share a short-lived snapshot.
_cache = {"ts": 0.0, "tasks": None, "lists": None}
_cache_lock = threading.Lock()


def tasks_snapshot(max_age=60):
    with _cache_lock:
        if _cache["tasks"] is None or time.time() - _cache["ts"] > max_age:
            _cache["tasks"] = list_all_tasks()
            _cache["lists"] = get_task_lists()
            _cache["ts"] = time.time()
        return [dict(t) for t in _cache["tasks"]], list(_cache["lists"])


def invalidate():
    with _cache_lock:
        _cache["tasks"] = None


_scoring = threading.Lock()


def score_in_background(tasks):
    """Difficulty-score new tasks without making the page wait for the AI"""
    missing = [t for t in tasks if store.cached_difficulty(t["id"], t["title"]) is None]
    if not missing or not _scoring.acquire(blocking=False):
        return

    def run():
        try:
            for t in missing:
                estimate_difficulty_and_minutes(t)
        finally:
            _scoring.release()

    threading.Thread(target=run, daemon=True).start()


def load_ranked(include_snoozed=False, include_hidden=False):
    """(ranked tasks, lists, error message or None)"""
    try:
        tasks, lists = tasks_snapshot()
    except Exception as e:
        logger.error(f"Google Tasks fetch failed: {e}")
        return [], [], "Can't reach Google Tasks. Check Settings → Google."
    score_in_background(tasks)
    ranked = picker.ranked(tasks, include_snoozed=include_snoozed, score_missing=False,
                           include_hidden=include_hidden)
    return ranked, lists, None


def find_task(task_id):
    try:
        tasks, _ = tasks_snapshot()
    except Exception:
        return None
    picker.enrich(tasks, score_missing=False)
    return next((t for t in tasks if t["id"] == task_id), None)


def current_routine(hour=None):
    hour = datetime.now().hour if hour is None else hour
    if 4 <= hour < 12:
        return "morning"
    if 12 <= hour < 21:
        return "evening"
    return "night"


def focus_pick(ranked):
    """The one task to show: a pinned focus if still open, else the top of the ranking"""
    pinned = store.get_setting("focus_task_id")
    if pinned:
        for t in ranked:
            if t["id"] == pinned:
                return t
    return ranked[0] if ranked else None


@app.context_processor
def inject_globals():
    return {
        "nav": request.endpoint,
        "due_label": picker.due_label,
        "PRIORITY_LABELS": picker.PRIORITY_LABELS,
        "DIFFICULTY_TEXT": picker.DIFFICULTY_TEXT,
    }


def ok(**data):
    return jsonify({"ok": True, **data})


def fail(message, status=400):
    return jsonify({"ok": False, "error": message}), status


# ===== PAGES =====
@app.route("/")
def now_page():
    ranked, lists, error = load_ranked()
    top = focus_pick(ranked)
    up_next = [t for t in ranked if top and t["id"] != top["id"]][:3]
    routine = current_routine()
    habits = store.habits(routine)
    checked = store.checked_habits()
    wins_today = [e for e in store.events_since(datetime.combine(date.today(), datetime.min.time()).astimezone())
                  if e["kind"] in ("task", "chore")]
    return render_template(
        "now.html", top=top, up_next=up_next, error=error, energy=store.energy_today(),
        timer=store.get_timer(), chores=store.overdue_chores()[:3], routine=routine,
        habits_done=sum(1 for h in habits if h["id"] in checked), habits_total=len(habits),
        wins_today=len(wins_today), streak=store.streak(),
        pinned=bool(top) and store.get_setting("focus_task_id") == top["id"],
    )


@app.route("/tasks")
def tasks_page():
    selected = request.args.get("list", "")
    ranked, lists, error = load_ranked(include_snoozed=True, include_hidden=bool(selected))
    hidden = picker.hidden_lists()
    shown = [t for t in ranked if not selected or t["list_id"] == selected]
    active = [t for t in shown if not t["snoozed"]]
    snoozed = [t for t in shown if t["snoozed"]]
    return render_template("tasks.html", active=active, snoozed=snoozed, lists=lists, hidden=hidden,
                           selected=selected, error=error)


@app.route("/chores")
def chores_page():
    rows = store.chores()
    return render_template(
        "chores.html",
        unknown=[c for c in rows if c["ratio"] is None],
        overdue=[c for c in rows if c["ratio"] is not None and c["ratio"] >= 1],
        upcoming=sorted([c for c in rows if c["ratio"] is not None and c["ratio"] < 1], key=lambda c: c["due_in"]),
    )


@app.route("/routines")
def routines_page():
    return render_template(
        "routines.html", routines={r: store.habits(r) for r in ROUTINES},
        checked=store.checked_habits(), current=current_routine(),
    )


@app.route("/wins")
def wins_page():
    week_start = datetime.combine(date.today() - timedelta(days=6), datetime.min.time()).astimezone()
    events = [e for e in store.events_since(week_start) if e["kind"] in ("task", "chore")]
    today = date.today().isoformat()
    by_day = store.wins_by_day(14)
    return render_template(
        "wins.html", today_events=[e for e in events if e["ts"][:10] == today],
        week_count=len(events), streak=store.streak(), by_day=by_day,
        max_day=max(by_day.values()) or 1,
    )


@app.route("/print")
def print_page():
    return render_template("print.html", online=receipts.printer_online(),
                           status=receipts.dispatch_status(), routine=current_routine())


@app.route("/settings")
def settings_page():
    try:
        lists = tasks_snapshot()[1]
    except Exception:
        lists = []
    import push
    return render_template(
        "settings.html", s=store.all_settings(), google=token_status(), lists=lists,
        hidden=picker.hidden_lists(),
        vapid_key=push.public_key(), subs=len(store.push_subs()),
    )


# ===== QR COMPLETION (kept compatible with printed receipts) =====
@app.route("/complete/<tasklist_id>/<task_id>")
def complete_task_endpoint(tasklist_id, task_id):
    task_name = request.args.get("name", "Task")
    logger.info(f"QR complete: {task_id} from list {tasklist_id}")
    success = complete_task(task_id, tasklist_id)
    if success:
        store.log_event("task", task_id, task_name)
        if store.get_setting("focus_task_id") == task_id:
            store.set_setting("focus_task_id", "")
        invalidate()
    return render_template("done.html", success=success, task_name=task_name, streak=store.streak())


@app.route("/health")
def health():
    return {"status": "ok", "message": "cyberPOS console is running"}


# ===== API: TASKS =====
@app.post("/api/capture")
def api_capture():
    import assistant
    text = (request.json or {}).get("text", "").strip()
    if not text:
        return fail("Nothing to capture")
    try:
        lists = tasks_snapshot()[1]
    except Exception:
        lists = []
    parsed = assistant.parse_capture(text, [title for _, title in lists])
    list_id = next((lid for lid, title in lists if title == parsed["list"]), None)
    try:
        task = create_task(parsed["title"], tasklist_id=list_id, notes=parsed["notes"] or None, due=parsed["due"])
    except Exception as e:
        return fail(f"Google said no: {e}", 502)
    store.upsert_task_meta(task["id"], priority=parsed["priority"])
    invalidate()
    return ok(task={"title": parsed["title"], "due": parsed["due"], "priority": parsed["priority"],
                    "list": parsed["list"] or (lists[0][1] if lists else "")})


@app.post("/api/task/<list_id>/<task_id>/done")
def api_task_done(list_id, task_id):
    t = find_task(task_id)
    if not complete_task(task_id, list_id):
        return fail("Couldn't mark it done in Google", 502)
    store.log_event("task", task_id, t["title"] if t else "Task")
    if store.get_setting("focus_task_id") == task_id:
        store.set_setting("focus_task_id", "")
    timer = store.get_timer()
    if timer and timer["task_id"] == task_id:
        store.clear_timer()
    invalidate()
    return ok(streak=store.streak())


@app.post("/api/task/<list_id>/<task_id>/snooze")
def api_task_snooze(list_id, task_id):
    when = (request.json or {}).get("until", "1h")
    now = store.now()
    if when == "1h":
        until = now + timedelta(hours=1)
    elif when == "tonight":
        until = now.replace(hour=18, minute=0, second=0, microsecond=0)
        if until <= now:
            until = now + timedelta(hours=2)
    elif when == "tomorrow":
        until = (now + timedelta(days=1)).replace(hour=6, minute=0, second=0, microsecond=0)
    elif when == "week":
        until = (now + timedelta(days=7)).replace(hour=6, minute=0, second=0, microsecond=0)
    elif when == "clear":
        until = None
    else:
        return fail("Unknown snooze")
    store.upsert_task_meta(task_id, snoozed_until=until.isoformat() if until else None)
    if store.get_setting("focus_task_id") == task_id:
        store.set_setting("focus_task_id", "")
    return ok()


@app.post("/api/task/<list_id>/<task_id>/priority")
def api_task_priority(list_id, task_id):
    priority = int((request.json or {}).get("priority", 2))
    if priority not in (1, 2, 3):
        return fail("Priority must be 1, 2 or 3")
    store.upsert_task_meta(task_id, priority=priority)
    return ok()


@app.post("/api/task/<list_id>/<task_id>/focus")
def api_task_focus(list_id, task_id):
    store.set_setting("focus_task_id", task_id)
    store.upsert_task_meta(task_id, snoozed_until=None)
    return ok()


@app.post("/api/focus/clear")
def api_focus_clear():
    store.set_setting("focus_task_id", "")
    return ok()


@app.post("/api/task/<list_id>/<task_id>/due")
def api_task_due(list_id, task_id):
    due = (request.json or {}).get("due") or ""
    try:
        update_task(task_id, list_id, due=due)
    except Exception as e:
        return fail(f"Google said no: {e}", 502)
    invalidate()
    return ok()


@app.post("/api/task/<list_id>/<task_id>/breakdown")
def api_task_breakdown(list_id, task_id):
    import assistant
    t = find_task(task_id)
    if not t:
        return fail("Task not found", 404)
    steps = assistant.breakdown(t["title"], t.get("notes", ""))
    if not steps:
        return fail("The AI couldn't break this down right now (check the Anthropic account). "
                    "Try writing the very first 2-minute step yourself.", 503)
    previous = None
    parent = t["parent"] or task_id  # Google Tasks only nests one level deep
    try:
        for step in steps:
            created = create_task(step, tasklist_id=list_id, parent=parent, previous=previous)
            previous = created["id"]
    except Exception as e:
        return fail(f"Google said no: {e}", 502)
    if store.get_setting("focus_task_id") == task_id:
        store.set_setting("focus_task_id", "")
    invalidate()
    return ok(steps=steps)


@app.post("/api/task/<list_id>/<task_id>/print")
def api_task_print(list_id, task_id):
    t = find_task(task_id)
    if not t:
        return fail("Task not found", 404)
    try:
        receipts.print_task_card(t)
    except Exception as e:
        return fail(f"Printer error: {e}", 502)
    return ok()


@app.post("/api/task/<list_id>/<task_id>/timer")
def api_task_timer(list_id, task_id):
    minutes = int((request.json or {}).get("minutes", 10))
    t = find_task(task_id)
    ends = store.start_timer(task_id, t["title"] if t else "Task", max(1, min(minutes, 180)))
    return ok(ends_at=ends.isoformat())


@app.post("/api/timer/extend")
def api_timer_extend():
    timer = store.get_timer()
    if not timer:
        return fail("No timer running")
    minutes = int((request.json or {}).get("minutes", 10))
    base = max(datetime.fromisoformat(timer["ends_at"]), store.now())
    store.conn().execute("UPDATE timer SET ends_at = ?, notified = 0 WHERE id = 1",
                         ((base + timedelta(minutes=minutes)).isoformat(),))
    store.conn().commit()
    return ok()


@app.post("/api/timer/stop")
def api_timer_stop():
    store.clear_timer()
    return ok()


@app.post("/api/energy")
def api_energy():
    level = (request.json or {}).get("level")
    if level not in ("low", "ok", "high"):
        return fail("Energy is low, ok or high")
    store.set_energy(level)
    return ok()


# ===== API: ROUTINES =====
@app.post("/api/habit/<int:habit_id>/toggle")
def api_habit_toggle(habit_id):
    return ok(on=store.toggle_habit(habit_id))


@app.post("/api/habit/add")
def api_habit_add():
    body = request.json or {}
    if body.get("routine") not in ROUTINES or not body.get("title", "").strip():
        return fail("Need a routine and a title")
    store.add_habit(body["routine"], body["title"].strip())
    return ok()


@app.post("/api/habit/<int:habit_id>/remove")
def api_habit_remove(habit_id):
    store.remove_habit(habit_id)
    return ok()


# ===== API: CHORES =====
@app.post("/api/chore/<int:chore_id>/done")
def api_chore_done(chore_id):
    store.chore_done(chore_id)
    return ok(streak=store.streak())


@app.post("/api/chore/<int:chore_id>/snooze")
def api_chore_snooze(chore_id):
    store.chore_snooze(chore_id, int((request.json or {}).get("days", 1)))
    return ok()


@app.post("/api/chore/<int:chore_id>/lastdone")
def api_chore_lastdone(chore_id):
    when = (request.json or {}).get("when")
    row = store.conn().execute("SELECT interval_days FROM chores WHERE id = ?", (chore_id,)).fetchone()
    if not row:
        return fail("Chore not found", 404)
    back = {"today": 0, "week": 3, "month": 15, "ages": row["interval_days"] * 2}.get(when)
    if back is None:
        return fail("Unknown answer")
    store.chore_set_last_done(chore_id, (date.today() - timedelta(days=back)).isoformat())
    return ok()


@app.post("/api/chore/add")
def api_chore_add():
    body = request.json or {}
    title, every = body.get("title", "").strip(), int(body.get("interval_days") or 7)
    if not title:
        return fail("Need a title")
    store.add_chore(title, max(1, every))
    return ok()


@app.post("/api/chore/<int:chore_id>/edit")
def api_chore_edit(chore_id):
    body = request.json or {}
    title, every = body.get("title", "").strip(), int(body.get("interval_days") or 7)
    if not title:
        return fail("Need a title")
    store.update_chore(chore_id, title, max(1, every))
    return ok()


@app.post("/api/chore/<int:chore_id>/remove")
def api_chore_remove(chore_id):
    store.remove_chore(chore_id)
    return ok()


# ===== API: PRINT =====
def _print(fn, *args):
    try:
        fn(*args)
    except Exception as e:
        return fail(f"Printer error: {e}", 502)
    return ok()


@app.post("/api/print/dispatch/<name>")
def api_print_dispatch(name):
    if name not in receipts.DISPATCHES:
        abort(404)
    return _print(receipts.run_dispatch, name)


@app.post("/api/print/note")
def api_print_note():
    text = (request.json or {}).get("text", "").strip()
    if not text:
        return fail("Nothing to print")
    return _print(receipts.print_note, text)


@app.post("/api/print/focus")
def api_print_focus():
    ranked, _, error = load_ranked()
    top = focus_pick(ranked)
    if not top:
        return fail(error or "No open tasks")
    return _print(receipts.print_task_card, top)


@app.post("/api/print/top")
def api_print_top():
    ranked, _, error = load_ranked()
    if not ranked:
        return fail(error or "No open tasks")
    items = [(t["title"], picker.due_label(t["due"]) or "") for t in ranked[:8]]
    return _print(receipts.print_checklist, "TOP TASKS", items)


@app.post("/api/print/chores")
def api_print_chores():
    overdue = store.overdue_chores()
    if not overdue:
        return fail("No chores overdue. Nice.")
    items = [(c["title"], f"{c['days_since']}D") for c in overdue]
    return _print(receipts.print_checklist, "CHORES DUE", items)


@app.post("/api/print/routine/<routine>")
def api_print_routine(routine):
    if routine not in ROUTINES:
        abort(404)
    return _print(receipts.print_checklist, f"{routine.upper()} ROUTINE", store.habit_titles(routine))


# ===== API: SETTINGS / PUSH / GOOGLE =====
SETTING_KEYS = {"nag_enabled", "nag_focus", "nag_focus_every_min", "nag_timer", "nag_chores",
                "nag_chores_at", "nag_alerts", "quiet_start", "quiet_end"}


@app.post("/api/settings")
def api_settings():
    body = request.json or {}
    for key, value in body.items():
        if key == "hidden_lists" and isinstance(value, list):
            store.set_setting(key, json.dumps(value))
        elif key in SETTING_KEYS:
            store.set_setting(key, value)
    return ok()


@app.post("/api/push/subscribe")
def api_push_subscribe():
    sub = request.json or {}
    if not sub.get("endpoint"):
        return fail("Bad subscription")
    store.add_push_sub(sub)
    return ok()


@app.post("/api/push/test")
def api_push_test():
    import push
    sent = push.send("cyberPOS", "Notifications are working. You can turn nags off in Settings.",
                     url="/settings", tag="test")
    return ok(sent=sent) if sent else fail("No phone subscribed yet")


@app.post("/api/google/reauth/start")
def api_reauth_start():
    try:
        return ok(url=reauth_start())
    except Exception as e:
        return fail(f"{type(e).__name__}: {e}", 500)


@app.post("/api/google/reauth/finish")
def api_reauth_finish():
    success, message = reauth_finish((request.json or {}).get("url", ""))
    if success:
        invalidate()
        return ok(message=message)
    return fail(message)


# ===== PWA =====
@app.route("/sw.js")
def service_worker():
    # Served from the root so its scope covers the whole app
    return app.send_static_file("sw.js"), 200, {"Cache-Control": "no-cache"}


@app.route("/manifest.webmanifest")
def manifest():
    return app.send_static_file("manifest.webmanifest"), 200, {"Content-Type": "application/manifest+json"}


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=False)
