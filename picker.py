"""
cyberPOS task picker.
Merges Google Tasks with local metadata (priority, snooze, cached difficulty) and ranks
everything so there is always exactly one "do this next" answer. Used by the console's
NOW screen and by the morning/evening dispatch receipts.
"""

import json
from datetime import date, datetime

import store
from google_tasks_helper import list_all_tasks, estimate_difficulty_and_minutes

PRIORITY_LABELS = {1: "HIGH", 2: "NORMAL", 3: "LOW"}
DIFFICULTY_TEXT = ["TRIVIAL", "VERY LIGHT", "LIGHT", "MODERATE", "HEAVY", "VERY HEAVY"]


def enrich(tasks, score_missing=True):
    """Attach priority / difficulty / minutes / snooze from the store to each task dict"""
    store.init()
    meta = store.all_task_meta()
    by_id = {t["id"]: t for t in tasks}
    children = {}
    for t in tasks:
        if t["parent"]:
            children.setdefault(t["parent"], []).append(t)

    now = store.now().isoformat()
    for t in tasks:
        m = meta.get(t["id"], {})
        parent = by_id.get(t["parent"]) if t["parent"] else None
        pm = meta.get(parent["id"], {}) if parent else {}
        # Subtasks inherit the parent's priority and due date unless they have their own
        t["priority"] = m.get("priority") or pm.get("priority") or 2
        if not t["due"] and parent:
            t["due"] = parent["due"]
        t["parent_title"] = parent["title"] if parent else None
        t["snoozed_until"] = m.get("snoozed_until")
        t["snoozed"] = bool(t["snoozed_until"] and t["snoozed_until"] > now)
        t["has_children"] = t["id"] in children
        if m.get("difficulty") is not None and m.get("title") == t["title"]:
            t["difficulty"], t["minutes"] = m["difficulty"], m.get("minutes")
        elif score_missing:
            t["difficulty"], t["minutes"] = estimate_difficulty_and_minutes(t)
        else:
            t["difficulty"], t["minutes"] = 2, None
        t["difficulty"] = max(0, min(5, int(t["difficulty"] or 0)))
    return tasks


def due_label(due):
    if not due:
        return ""
    d = (date.fromisoformat(due) - date.today()).days
    if d < 0:
        return f"{-d}D OVERDUE"
    return {0: "TODAY", 1: "TOMORROW"}.get(d, f"IN {d}D")


def score(t, energy=None):
    s = 0.0
    if t["due"]:
        d = (date.fromisoformat(t["due"]) - date.today()).days
        if d < 0:
            s += 100 + min(-d, 14) * 2
        elif d == 0:
            s += 80
        elif d == 1:
            s += 40
        elif d <= 3:
            s += 20
    s += {1: 60, 2: 30, 3: 0}.get(t["priority"], 30)

    diff = t["difficulty"]
    if energy == "low":
        s += {0: 25, 1: 25, 2: 15, 3: 0, 4: -20, 5: -40}[diff]
    elif energy == "high":
        s += {0: -5, 1: 0, 2: 5, 3: 10, 4: 20, 5: 20}[diff]
    else:
        s += {0: 5, 1: 5, 2: 8, 3: 5, 4: 0, 5: -5}[diff]

    # Older tasks slowly float up so nothing rots at the bottom forever
    try:
        age = (datetime.now().astimezone() - datetime.fromisoformat(t["updated"].replace("Z", "+00:00"))).days
        s += min(age, 14)
    except (ValueError, KeyError, AttributeError):
        pass
    # Steps from a broken-down task are small by design: nudge them up
    if t["parent"]:
        s += 5
    return s


def hidden_lists():
    """Task lists the user excluded from picking (e.g. a grocery list)"""
    store.init()
    try:
        return set(json.loads(store.get_setting("hidden_lists", "[]")))
    except ValueError:
        return set()


def ranked(tasks=None, energy=None, include_snoozed=False, score_missing=True, include_hidden=False):
    """
    Actionable tasks, best first. Parents that have open subtasks are skipped
    (their next subtask is the actionable thing), as are lists hidden in Settings.
    """
    if tasks is None:
        tasks = list_all_tasks()
    if not include_hidden:
        hidden = hidden_lists()
        tasks = [t for t in tasks if t["list_id"] not in hidden]
    enrich(tasks, score_missing=score_missing)
    if energy is None:
        energy = store.energy_today()
    out = [t for t in tasks if not t["has_children"] and (include_snoozed or not t["snoozed"])]
    for t in out:
        t["score"] = score(t, energy)
    out.sort(key=lambda t: (-t["score"], t["position"]))
    return out


def as_dispatch_tuples(tasks):
    """(task_id, tasklist_id, title, difficulty) like get_tasks_with_ids, for the receipt scripts"""
    return [(t["id"], t["list_id"], t["title"], t["difficulty"]) for t in tasks]


def dispatch_queue(max_tasks=10):
    """
    (primary, remaining) for the receipt scripts, as (task_id, tasklist_id, title, difficulty)
    tuples. The primary objective is the console's pinned focus if set, else the top pick.
    """
    tasks = ranked()[:max_tasks + 1]
    if not tasks:
        return None, []
    pinned = store.get_setting("focus_task_id")
    primary = next((t for t in tasks if t["id"] == pinned), tasks[0])
    rest = [t for t in tasks if t is not primary][:max_tasks - 1]
    return as_dispatch_tuples([primary])[0], as_dispatch_tuples(rest)
