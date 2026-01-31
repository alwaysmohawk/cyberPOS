"""
cyberPOS — EVENING DISPATCH
Evening briefing: primary objective, habits, weather, calendar, task queue
"""

from datetime import datetime
import random
from google_tasks_helper import get_tasks_with_ids, get_calendar_events
from weather import get_weather
from printer import p, raw, invert, MAJOR, MINOR, print_logo, diff_ascii, line_item, wrap_task

# ===== CONFIG =====
MAX_TASKS = 10

# ===== HABITS =====
HABITS = [
    "Walk Neptune",
    "Tidy the space",
    "Review today's tasks",
    "Lay out tomorrow's clothes",
    "Prep lunch for tomorrow",
    "Stretch for 10 min",
]

# ===== FOOTERS =====
FOOTERS = [
    "GOOD DAY. REST EARNED.",
    "CLOSE THE LOOP. PREP FOR TOMORROW.",
    "TONIGHT'S SETUP = TOMORROW'S WIN.",
    "SMALL WINS ADD UP.",
    "DONE FOR TODAY. WELL EARNED.",
    "SET YOURSELF UP. THEN REST.",
    "WRAP IT UP. YOU EARNED IT.",
    "TOMORROW STARTS TONIGHT.",
]

def main():
    now = datetime.now()

    # --- Fetch all data ---
    print("Fetching tasks...")
    tasks = get_tasks_with_ids(max_results=MAX_TASKS)

    print("Fetching calendar...")
    calendar = get_calendar_events()

    print("Fetching weather...")
    weather = get_weather()

    # --- Primary objective = highest difficulty task ---
    primary = None
    remaining = []
    if tasks:
        sorted_tasks = sorted(tasks, key=lambda t: t[3], reverse=True)
        primary = sorted_tasks[0]
        remaining = sorted_tasks[1:]

    # ===== BEGIN PRINT =====
    p.open()
    raw("1B 40")  # ESC @ init

    # --- LOGO ---
    print_logo()

    # --- TITLE ---
    raw("1D 21 11")  # 2x2
    p.text("EVENING DISPATCH\n")
    raw("1D 21 00")

    p.text("fastAF industries :: NODE 01\n")
    p.text("TORONTO // SECTOR 416\n")
    p.text(MAJOR + "\n")

    # --- META ---
    p.set(align="left")
    p.text(f"DATE {now:%Y-%m-%d}".ljust(32) + f"TIME {now:%H:%M}\n")
    p.text(f"{now:%A}".ljust(32) + "OP ALEXANDER\n")
    p.text(MAJOR + "\n")

    # --- PRIMARY OBJECTIVE ---
    p.set(align="center")
    invert(True)
    p.text(" PRIMARY OBJECTIVE ".center(48) + "\n")
    invert(False)
    p.set(align="left")
    p.text("\n")

    if primary:
        _, _, title, difficulty = primary
        lines = wrap_task(title)
        p.text(line_item(f"[ ] {lines[0]}", diff_ascii(difficulty)))
        for line in lines[1:]:
            p.text(f"    {line}\n")
    else:
        p.text("  Nothing queued.\n")

    p.text("\n")
    p.text(MAJOR + "\n")

    # --- HABITS ---
    p.text("EVENING HABITS\n")
    p.text(MINOR + "\n")
    for habit in HABITS:
        p.text(f"[ ] {habit}\n")
    p.text(MINOR + "\n")

    # --- WEATHER ---
    p.text("WEATHER\n")
    p.text(MINOR + "\n")
    if weather:
        p.text(f"{weather['condition']}  {weather['temp']}C now\n")
        hi_lo = f"H: {weather['temp_high']}C  L: {weather['temp_low']}C"
        wind = f"Wind: {weather['wind_speed']}km/h {weather['wind_dir']}"
        p.text(f"{hi_lo}".ljust(24) + f"{wind}\n")
        p.text(f"Precip: {weather['precip']}%\n")
    else:
        p.text("  Weather unavailable\n")
    p.text(MINOR + "\n")

    # --- CALENDAR ---
    p.text("CALENDAR\n")
    p.text(MINOR + "\n")
    if calendar:
        for time_str, title, is_all_day in calendar:
            max_title = 48 - len(time_str) - 2
            p.text(f"{time_str}  {title[:max_title]}\n")
    else:
        p.text("  Nothing scheduled\n")
    p.text(MAJOR + "\n")

    # --- TASK QUEUE (remaining after primary) ---
    if remaining:
        p.text(line_item("TASK QUEUE", f"{len(remaining)} LEFT"))
        p.text(MINOR + "\n")
        for _, _, title, difficulty in remaining:
            p.text(line_item(f"[ ] {title}", diff_ascii(difficulty)))
        p.text(MAJOR + "\n")

    # --- FOOTER ---
    p.set(align="center")
    p.text(random.choice(FOOTERS) + "\n")

    p.cut()
    p.close()

if __name__ == "__main__":
    main()
