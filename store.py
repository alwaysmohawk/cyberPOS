"""
cyberPOS local state (SQLite).
Google Tasks stays the source of truth for tasks; this holds everything Google doesn't:
priorities, snoozes, cached difficulty, habits, chores, energy, timers, push subscriptions,
settings and the wins log. Shared by the console, the nagger and the dispatch scripts.
"""

import json
import sqlite3
import threading
from datetime import datetime, date, timedelta
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent / "cyberpos.db"

_local = threading.local()

SCHEMA = """
CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT);
CREATE TABLE IF NOT EXISTS task_meta (
    task_id TEXT PRIMARY KEY, title TEXT, difficulty INTEGER, minutes INTEGER,
    priority INTEGER DEFAULT 2, snoozed_until TEXT, updated_at TEXT, ai_scored INTEGER DEFAULT 0);
CREATE TABLE IF NOT EXISTS events (
    id INTEGER PRIMARY KEY, ts TEXT, kind TEXT, ref TEXT, title TEXT);
CREATE TABLE IF NOT EXISTS habits (
    id INTEGER PRIMARY KEY, routine TEXT, title TEXT, sort INTEGER, active INTEGER DEFAULT 1);
CREATE TABLE IF NOT EXISTS habit_checks (habit_id INTEGER, day TEXT, PRIMARY KEY (habit_id, day));
CREATE TABLE IF NOT EXISTS chores (
    id INTEGER PRIMARY KEY, title TEXT, interval_days INTEGER, last_done TEXT,
    snoozed_until TEXT, active INTEGER DEFAULT 1);
CREATE TABLE IF NOT EXISTS energy (day TEXT PRIMARY KEY, level TEXT);
CREATE TABLE IF NOT EXISTS timer (
    id INTEGER PRIMARY KEY CHECK (id = 1), task_id TEXT, title TEXT, ends_at TEXT, notified INTEGER DEFAULT 0);
CREATE TABLE IF NOT EXISTS push_subs (endpoint TEXT PRIMARY KEY, data TEXT, created_at TEXT);
CREATE TABLE IF NOT EXISTS nag_log (kind TEXT PRIMARY KEY, last_sent TEXT, ref TEXT);
"""

# Seeded from the habit lists that used to be hardcoded in the dispatch scripts
DEFAULT_HABITS = {
    "morning": ["Eat breakfast", "Take vitamins", "Brush teeth", "Walk Neptune",
                "Drink water", "Move your body"],
    "evening": ["Walk Neptune", "Tidy the space", "Review today's tasks",
                "Lay out tomorrow's clothes", "Prep lunch for tomorrow", "Stretch for 10 min"],
    "night": ["Brush teeth", "Wash face", "Set tomorrow's alarm", "Write 3 gratitudes",
              "Drink water", "No screens — wind down"],
}

# (title, every N days). last_done starts empty; the console asks once when each was last done.
DEFAULT_CHORES = [
    ("Run the dishwasher / do dishes", 2),
    ("Wipe kitchen counters + stove", 3),
    ("Take out trash + recycling", 4),
    ("Wash Neptune's bowls", 3),
    ("Laundry: wash, dry, FOLD, put away", 7),
    ("Wash towels", 7),
    ("Clean toilet + bathroom sink", 7),
    ("Vacuum floors", 7),
    ("Toss expired food from fridge", 7),
    ("Grocery run", 7),
    ("Empty bathroom + bedroom bins", 7),
    ("Change bed sheets", 14),
    ("Clean shower / tub", 14),
    ("Mop floors", 14),
    ("Dust surfaces", 14),
    ("Wipe mirrors", 14),
    ("Wash bath mats", 30),
    ("Wash Neptune's bed", 30),
    ("Clean microwave", 30),
    ("Clean dishwasher filter", 30),
    ("Descale kettle / coffee maker", 60),
    ("Replace toothbrush head", 90),
    ("Clean range hood filter", 90),
    ("Test smoke detector", 180),
]

DEFAULT_SETTINGS = {
    "nag_enabled": "1",
    "nag_focus": "1",            # "your one thing" reminders during active hours
    "nag_focus_every_min": "120",
    "nag_timer": "1",            # timer finished
    "nag_chores": "1",           # daily overdue-chores reminder
    "nag_chores_at": "18:00",
    "nag_alerts": "1",           # dispatch / Google connection failures
    "quiet_start": "22:30",
    "quiet_end": "09:00",
}


def conn():
    c = getattr(_local, "conn", None)
    if c is None:
        c = sqlite3.connect(DB_PATH, timeout=10)
        c.row_factory = sqlite3.Row
        c.execute("PRAGMA journal_mode=WAL")
        _local.conn = c
    return c


_initialized = False


def init():
    global _initialized
    if _initialized:
        return
    c = conn()
    c.executescript(SCHEMA)
    for k, v in DEFAULT_SETTINGS.items():
        c.execute("INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)", (k, v))
    if not c.execute("SELECT 1 FROM habits LIMIT 1").fetchone():
        for routine, items in DEFAULT_HABITS.items():
            for i, title in enumerate(items):
                c.execute("INSERT INTO habits (routine, title, sort) VALUES (?, ?, ?)", (routine, title, i))
    if not c.execute("SELECT 1 FROM chores LIMIT 1").fetchone():
        for title, every in DEFAULT_CHORES:
            c.execute("INSERT INTO chores (title, interval_days) VALUES (?, ?)", (title, every))
    c.commit()
    _initialized = True


def now():
    return datetime.now().astimezone()


def today():
    return date.today().isoformat()


# ===== SETTINGS =====
def get_setting(key, default=None):
    row = conn().execute("SELECT value FROM settings WHERE key = ?", (key,)).fetchone()
    return row["value"] if row else default


def set_setting(key, value):
    conn().execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", (key, str(value)))
    conn().commit()


def all_settings():
    return {r["key"]: r["value"] for r in conn().execute("SELECT key, value FROM settings")}


# ===== TASK META =====
def get_task_meta(task_id):
    row = conn().execute("SELECT * FROM task_meta WHERE task_id = ?", (task_id,)).fetchone()
    return dict(row) if row else None


def all_task_meta():
    return {r["task_id"]: dict(r) for r in conn().execute("SELECT * FROM task_meta")}


def upsert_task_meta(task_id, **fields):
    c = conn()
    existing = get_task_meta(task_id)
    fields["updated_at"] = now().isoformat()
    if existing:
        sets = ", ".join(f"{k} = ?" for k in fields)
        c.execute(f"UPDATE task_meta SET {sets} WHERE task_id = ?", (*fields.values(), task_id))
    else:
        cols = ", ".join(["task_id", *fields])
        marks = ", ".join("?" * (len(fields) + 1))
        c.execute(f"INSERT INTO task_meta ({cols}) VALUES ({marks})", (task_id, *fields.values()))
    c.commit()


def cached_difficulty(task_id, title):
    """Return (difficulty, minutes) if this task's title was already scored, else None"""
    m = get_task_meta(task_id) if task_id else None
    if not m or m["title"] != title or m["difficulty"] is None:
        return None
    # Keyword-fallback guesses are retried after a while in case the AI is back
    if not m["ai_scored"] and m["updated_at"] < (now() - timedelta(hours=6)).isoformat():
        return None
    return m["difficulty"], m["minutes"]


# ===== EVENTS (wins log) =====
def log_event(kind, ref, title):
    conn().execute("INSERT INTO events (ts, kind, ref, title) VALUES (?, ?, ?, ?)",
                   (now().isoformat(), kind, ref, title))
    conn().commit()


def events_since(since):
    return [dict(r) for r in conn().execute(
        "SELECT * FROM events WHERE ts >= ? ORDER BY ts DESC", (since.isoformat(),))]


def last_event_ts(kinds=("task", "timer_start")):
    marks = ",".join("?" * len(kinds))
    row = conn().execute(f"SELECT MAX(ts) AS ts FROM events WHERE kind IN ({marks})", kinds).fetchone()
    return datetime.fromisoformat(row["ts"]) if row and row["ts"] else None


def wins_by_day(days=14):
    start = date.today() - timedelta(days=days - 1)
    counts = {(start + timedelta(d)).isoformat(): 0 for d in range(days)}
    for r in conn().execute(
            "SELECT substr(ts, 1, 10) AS d, COUNT(*) AS n FROM events "
            "WHERE kind IN ('task', 'chore') AND ts >= ? GROUP BY d", (start.isoformat(),)):
        if r["d"] in counts:
            counts[r["d"]] = r["n"]
    return counts


def streak():
    """Consecutive days (ending today, or yesterday if nothing yet today) with at least one win"""
    days = {r["d"] for r in conn().execute(
        "SELECT DISTINCT substr(ts, 1, 10) AS d FROM events WHERE kind IN ('task', 'chore')")}
    d = date.today()
    if d.isoformat() not in days:
        d -= timedelta(days=1)
    n = 0
    while d.isoformat() in days:
        n += 1
        d -= timedelta(days=1)
    return n


# ===== HABITS =====
def habits(routine, active_only=True):
    q = "SELECT * FROM habits WHERE routine = ?" + (" AND active = 1" if active_only else "") + " ORDER BY sort, id"
    return [dict(r) for r in conn().execute(q, (routine,))]


def habit_titles(routine):
    return [h["title"] for h in habits(routine)] or DEFAULT_HABITS.get(routine, [])


def checked_habits(day=None):
    return {r["habit_id"] for r in conn().execute(
        "SELECT habit_id FROM habit_checks WHERE day = ?", (day or today(),))}


def toggle_habit(habit_id, day=None):
    c, day = conn(), day or today()
    if c.execute("SELECT 1 FROM habit_checks WHERE habit_id = ? AND day = ?", (habit_id, day)).fetchone():
        c.execute("DELETE FROM habit_checks WHERE habit_id = ? AND day = ?", (habit_id, day))
        on = False
    else:
        c.execute("INSERT INTO habit_checks (habit_id, day) VALUES (?, ?)", (habit_id, day))
        on = True
    c.commit()
    return on


def add_habit(routine, title):
    c = conn()
    sort = c.execute("SELECT COALESCE(MAX(sort), -1) + 1 FROM habits WHERE routine = ?", (routine,)).fetchone()[0]
    c.execute("INSERT INTO habits (routine, title, sort) VALUES (?, ?, ?)", (routine, title, sort))
    c.commit()


def remove_habit(habit_id):
    conn().execute("UPDATE habits SET active = 0 WHERE id = ?", (habit_id,))
    conn().commit()


# ===== CHORES =====
def chores(include_inactive=False):
    """All chores with computed fields, most overdue first"""
    rows = [dict(r) for r in conn().execute(
        "SELECT * FROM chores" + ("" if include_inactive else " WHERE active = 1"))]
    t = date.today()
    for ch in rows:
        ch["snoozed"] = bool(ch["snoozed_until"] and ch["snoozed_until"] > t.isoformat())
        if ch["last_done"]:
            days = (t - date.fromisoformat(ch["last_done"])).days
            ch["days_since"] = days
            ch["ratio"] = days / max(ch["interval_days"], 1)
            ch["due_in"] = ch["interval_days"] - days
        else:
            ch["days_since"] = None
            ch["ratio"] = None
            ch["due_in"] = None
    rows.sort(key=lambda ch: (ch["ratio"] is None, -(ch["ratio"] or 0)))
    return rows


def overdue_chores():
    return [ch for ch in chores() if ch["ratio"] is not None and ch["ratio"] >= 1 and not ch["snoozed"]]


def chore_done(chore_id, day=None):
    c = conn()
    c.execute("UPDATE chores SET last_done = ?, snoozed_until = NULL WHERE id = ?", (day or today(), chore_id))
    c.commit()
    row = c.execute("SELECT title FROM chores WHERE id = ?", (chore_id,)).fetchone()
    if row and (day is None or day == today()):
        log_event("chore", str(chore_id), row["title"])


def chore_set_last_done(chore_id, day):
    conn().execute("UPDATE chores SET last_done = ? WHERE id = ?", (day, chore_id))
    conn().commit()


def chore_snooze(chore_id, days=1):
    until = (date.today() + timedelta(days=days)).isoformat()
    conn().execute("UPDATE chores SET snoozed_until = ? WHERE id = ?", (until, chore_id))
    conn().commit()


def add_chore(title, interval_days):
    conn().execute("INSERT INTO chores (title, interval_days) VALUES (?, ?)", (title, interval_days))
    conn().commit()


def update_chore(chore_id, title, interval_days):
    conn().execute("UPDATE chores SET title = ?, interval_days = ? WHERE id = ?", (title, interval_days, chore_id))
    conn().commit()


def remove_chore(chore_id):
    conn().execute("UPDATE chores SET active = 0 WHERE id = ?", (chore_id,))
    conn().commit()


# ===== ENERGY =====
def energy_today():
    row = conn().execute("SELECT level FROM energy WHERE day = ?", (today(),)).fetchone()
    return row["level"] if row else None


def set_energy(level):
    conn().execute("INSERT OR REPLACE INTO energy (day, level) VALUES (?, ?)", (today(), level))
    conn().commit()


# ===== TIMER =====
def get_timer():
    row = conn().execute("SELECT * FROM timer WHERE id = 1").fetchone()
    return dict(row) if row else None


def start_timer(task_id, title, minutes):
    ends = now() + timedelta(minutes=minutes)
    conn().execute("INSERT OR REPLACE INTO timer (id, task_id, title, ends_at, notified) VALUES (1, ?, ?, ?, 0)",
                   (task_id, title, ends.isoformat()))
    conn().commit()
    log_event("timer_start", task_id, title)
    return ends


def clear_timer():
    conn().execute("DELETE FROM timer WHERE id = 1")
    conn().commit()


def mark_timer_notified():
    conn().execute("UPDATE timer SET notified = 1 WHERE id = 1")
    conn().commit()


# ===== PUSH =====
def add_push_sub(sub):
    conn().execute("INSERT OR REPLACE INTO push_subs (endpoint, data, created_at) VALUES (?, ?, ?)",
                   (sub["endpoint"], json.dumps(sub), now().isoformat()))
    conn().commit()


def push_subs():
    return [json.loads(r["data"]) for r in conn().execute("SELECT data FROM push_subs")]


def remove_push_sub(endpoint):
    conn().execute("DELETE FROM push_subs WHERE endpoint = ?", (endpoint,))
    conn().commit()


# ===== NAG LOG =====
def nag_last(kind):
    row = conn().execute("SELECT last_sent, ref FROM nag_log WHERE kind = ?", (kind,)).fetchone()
    return (datetime.fromisoformat(row["last_sent"]), row["ref"]) if row else (None, None)


def nag_mark(kind, ref=None):
    conn().execute("INSERT OR REPLACE INTO nag_log (kind, last_sent, ref) VALUES (?, ?, ?)",
                   (kind, now().isoformat(), ref))
    conn().commit()
