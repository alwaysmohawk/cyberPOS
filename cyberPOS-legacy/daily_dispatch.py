"""
cyberPOS — DAILY DISPATCH
Morning briefing: primary objective, habits, weather, calendar, task queue
"""

from escpos.printer import Network
from datetime import datetime
from PIL import Image
import random
import urllib.request
import json
from google_tasks_helper import get_tasks_with_ids, get_calendar_events

# ===== CONFIG =====
PRINTER_IP = "192.168.88.154"
PRINTER_PORT = 9100
LOGO_BMP_PATH = "fastaf_nv.bmp"
MAX_TASKS = 10

# ===== HABITS =====
HABITS = [
    "Eat breakfast",
    "Take vitamins",
    "Brush teeth",
    "Walk Neptune",
    "Drink water",
    "Move your body",
]

# ===== WEATHER =====
WEATHER_CODES = {
    0: "Clear Sky",         1: "Mainly Clear",     2: "Partly Cloudy",
    3: "Overcast",          45: "Foggy",            48: "Rime Fog",
    51: "Light Drizzle",    53: "Drizzle",          55: "Dense Drizzle",
    61: "Slight Rain",      63: "Moderate Rain",    65: "Heavy Rain",
    71: "Slight Snow",      73: "Moderate Snow",    75: "Heavy Snow",
    77: "Snow Grains",      80: "Slight Showers",   81: "Mod. Showers",
    82: "Violent Showers",  85: "Snow Showers",     86: "Heavy Snow Showers",
    95: "Thunderstorm",     96: "T-Storm + Hail",   99: "T-Storm + Heavy Hail",
}

def wind_dir(degrees):
    dirs = ["N", "NE", "E", "SE", "S", "SW", "W", "NW"]
    return dirs[round(degrees / 45) % 8]

def get_weather():
    """Fetch Toronto weather from Open-Meteo (free, no API key needed)"""
    url = (
        "https://api.open-meteo.com/v1/forecast"
        "?latitude=43.6532&longitude=-79.3832"
        "&current_weather=true"
        "&hourly=temperature_2m,precipitation_probability"
        "&timezone=America/Toronto"
        "&forecast_days=1"
    )
    try:
        with urllib.request.urlopen(url, timeout=5) as resp:
            data = json.loads(resp.read())

        current = data['current_weather']
        hourly = data['hourly']
        temps = hourly['temperature_2m']
        precip = max(hourly['precipitation_probability'])

        return {
            'condition': WEATHER_CODES.get(current['weathercode'], 'Unknown'),
            'temp': round(current['temperature']),
            'temp_high': round(max(temps)),
            'temp_low': round(min(temps)),
            'wind_speed': int(current['windspeed']),
            'wind_dir': wind_dir(current['winddirection']),
            'precip': round(precip),
        }
    except Exception as e:
        print(f"Warning: Weather fetch failed ({e})")
        return None

# ===== PRINTER =====
p = Network(PRINTER_IP, PRINTER_PORT, profile="default")

def raw(hexstr: str):
    p._raw(bytes.fromhex(hexstr))

def invert(on: bool):
    raw("1D 42 01" if on else "1D 42 00")

MAJOR = "=" * 48
MINOR = "-" * 48

def diff_ascii(level: int) -> str:
    return "[" + ("*" * level).ljust(5, ".") + "]"

def line_item(left: str, right: str) -> str:
    right = right.rjust(6)
    max_left = 48 - len(right) - 1
    left = left[:max_left]
    dots = "." * max(1, (48 - len(left) - len(right) - 1))
    return f"{left} {dots}{right}\n"

def wrap_task(title, max_width=35):
    """Word-wrap a task title into lines"""
    if len(title) <= max_width:
        return [title]
    words = title.split()
    lines, current = [], ""
    for word in words:
        if len(current) + len(word) + 1 <= max_width:
            current += word + " "
        else:
            if current:
                lines.append(current.strip())
            current = word + " "
    if current:
        lines.append(current.strip())
    return lines

# ===== FOOTERS =====
FOOTERS = [
    "HYDRATE. MOVE. BREATHE.",
    "ONE THING AT A TIME. START NOW.",
    "YOU KNOW WHAT TO DO. DO IT.",
    "PROGRESS. NOT PERFECTION.",
    "JUST START. THE REST FOLLOWS.",
    "PICK ONE. GO.",
    "SMALL STEPS. KEEP MOVING.",
    "DONE BEATS PERFECT.",
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
    p.set(align="center")

    invert(True)
    p.text(" " * 48 + "\n")
    invert(False)

    logo = Image.open(LOGO_BMP_PATH)
    if logo.mode not in ("1", "L"):
        logo = logo.convert("1")
    p.image(logo)

    invert(True)
    p.text(" " * 48 + "\n")
    invert(False)

    p.text("\n")

    # --- TITLE ---
    raw("1D 21 11")  # 2x2
    p.text("DAILY DISPATCH\n")
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
    p.text("DAILY HABITS\n")
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
