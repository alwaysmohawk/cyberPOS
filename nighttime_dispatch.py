"""
cyberPOS — NIGHT DISPATCH
Pre-sleep checklist with tomorrow's weather and calendar
"""

from datetime import datetime
import random
from google_tasks_helper import get_calendar_events
from weather import get_tomorrow_weather
from printer import p, raw, invert, MAJOR, MINOR, print_logo

# ===== HABITS =====
HABITS = [
    "Brush teeth",
    "Wash face",
    "Set tomorrow's alarm",
    "Write 3 gratitudes",
    "Drink water",
    "No screens — wind down",
]

# ===== FOOTERS =====
FOOTERS = [
    "LIGHTS OUT. RECHARGE.",
    "SLEEP IS THE RESET. TAKE IT.",
    "TOMORROW IS WAITING. REST NOW.",
    "GOOD NIGHT. YOU DID ENOUGH.",
    "REST. RECOVER. REPEAT.",
    "SHUT IT DOWN. WELL EARNED.",
    "CLOSE YOUR EYES. REBOOT TOMORROW.",
    "YOU SHOWED UP TODAY. THAT COUNTS.",
]

def main():
    now = datetime.now()

    # --- Fetch data ---
    print("Fetching tomorrow's calendar...")
    calendar = get_calendar_events(days_offset=1)

    print("Fetching tomorrow's weather...")
    weather = get_tomorrow_weather()

    # ===== BEGIN PRINT =====
    p.open()
    raw("1B 40")  # ESC @ init

    # --- LOGO ---
    print_logo()

    # --- TITLE ---
    raw("1D 21 11")  # 2x2
    p.text("NIGHT DISPATCH\n")
    raw("1D 21 00")

    p.text("fastAF industries :: NODE 01\n")
    p.text("TORONTO // SECTOR 416\n")
    p.text(MAJOR + "\n")

    # --- META ---
    p.set(align="left")
    p.text(f"DATE {now:%Y-%m-%d}".ljust(32) + f"TIME {now:%H:%M}\n")
    p.text(f"{now:%A}".ljust(32) + "OP ALEXANDER\n")
    p.text(MAJOR + "\n")

    # --- NIGHTTIME HABITS ---
    p.set(align="center")
    invert(True)
    p.text(" NIGHTTIME HABITS ".center(48) + "\n")
    invert(False)
    p.set(align="left")
    p.text("\n")

    for habit in HABITS:
        p.text(f"[ ] {habit}\n")

    p.text("\n")
    p.text(MAJOR + "\n")

    # --- TOMORROW'S WEATHER ---
    p.text("TOMORROW'S WEATHER\n")
    p.text(MINOR + "\n")
    if weather:
        p.text(f"{weather['condition']}\n")
        hi_lo = f"H: {weather['temp_high']}C  L: {weather['temp_low']}C"
        wind = f"Wind: {weather['wind_speed']}km/h {weather['wind_dir']}"
        p.text(f"{hi_lo}".ljust(24) + f"{wind}\n")
        p.text(f"Precip: {weather['precip']}%\n")
    else:
        p.text("  Weather unavailable\n")
    p.text(MINOR + "\n")

    # --- TOMORROW'S CALENDAR ---
    p.text("TOMORROW'S CALENDAR\n")
    p.text(MINOR + "\n")
    if calendar:
        for time_str, title, is_all_day in calendar:
            max_title = 48 - len(time_str) - 2
            p.text(f"{time_str}  {title[:max_title]}\n")
    else:
        p.text("  Nothing scheduled\n")
    p.text(MAJOR + "\n")

    # --- FOOTER ---
    p.set(align="center")
    p.text(random.choice(FOOTERS) + "\n")

    p.cut()
    p.close()

if __name__ == "__main__":
    main()
