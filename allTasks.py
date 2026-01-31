from escpos.printer import Network
from datetime import datetime
from PIL import Image
import random
from google_tasks_helper import get_tasks_for_printer

# ===== CONFIG =====
PRINTER_IP = "192.168.88.154"
PRINTER_PORT = 9100
LOGO_BMP_PATH = "fastaf_nv.bmp"

RECEIPT_NO = 21
MAX_TASKS = 10  # Maximum number of tasks to print

# ===== PRINTER =====
p = Network(PRINTER_IP, PRINTER_PORT, profile="default")

def raw(hexstr: str):
    p._raw(bytes.fromhex(hexstr))

def invert(on: bool):
    # GS B n — invert print (safe if unsupported)
    raw("1D 42 01" if on else "1D 42 00")

MAJOR = "=" * 48
MINOR = "-" * 48

def diff_ascii(level: int) -> str:
    # Difficulty indicator: [.....] [*.....] [**....] [***...] [****..] [*****.]
    return "[" + ("*" * level).ljust(5, ".") + "]"

def line_item(left: str, right: str) -> str:
    right = right.rjust(6)
    max_left = 48 - len(right) - 1
    left = left[:max_left]
    dots = "." * max(1, (48 - len(left) - len(right) - 1))
    return f"{left} {dots}{right}\n"

# ===== FOOTERS =====
FOOTERS = [
    # --- Set A ---
    "DONE IS BETTER THAN PERFECT.",
    "DONE BEATS PERFECT. EVERY TIME.",
    "FINISHED > PERFECT.",
    "DONE COUNTS. PERFECTION CAN WAIT.",
    "PROGRESS OVER PERFECTION.",
    "DONE FIRST. PERFECT LATER.",

    # --- Set B ---
    "YOU’RE MAKING PROGRESS. KEEP GOING.",
    "ONE STEP IS STILL A STEP.",
    "SMALL WINS ADD UP.",
    "STEADY BEATS FAST.",
    "KEEP GOING. YOU’RE ON TRACK.",
    "THANK YOU FOR TAKING THIS ON.",
    "YOU’VE GOT THIS.",

    # --- Custom ---
    "YOUR EFFORTS ARE APPRECIATED.",
    "YOU ARE ENOUGH.",
    "THANK YOU.",
    "GOOD WORK, OPERATOR.",
]

def main():
    now = datetime.now()

    # Fetch tasks from Google Tasks
    print("Fetching tasks from Google Tasks...")
    tasks = get_tasks_for_printer(max_results=MAX_TASKS)

    # Fallback to sample tasks if no tasks found
    if not tasks:
        print("No tasks found in Google Tasks. Using sample tasks.")
        tasks = [
            ("NO TASKS FOUND - ADD SOME!", 1),
        ]

    total_load = sum(lvl for _, lvl in tasks)
    task_count = len(tasks)

    p.open()
    raw("1B 40")  # ESC @ init

    # ===== OPTION B HEADER =====
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

    # Spacer line (intentional breathing room)
    p.text("\n")

    # ===== TITLE =====
    raw("1D 21 11")  # 2x2
    p.text("THERMAL TASK NODE\n")
    raw("1D 21 00")

    p.text("fastAF industries :: NODE 01\n")
    p.text("TORONTO // SECTOR 416\n")
    p.text(MAJOR + "\n")

    # ===== META =====
    p.set(align="left")
    p.text(f"DATE {now:%Y-%m-%d}".ljust(32) + f"TIME {now:%H:%M}\n")
    p.text(f"RECEIPT #{RECEIPT_NO:06d}".ljust(32) + "OP ALEXANDER\n")
    p.text(MINOR + "\n")

    # ===== TASKS =====
    for name, lvl in tasks:
        p.text(line_item(f"[ ] {name}", diff_ascii(lvl)))

    p.text(MAJOR + "\n")

    # ===== TOTALS =====
    total_bucket = min(max(total_load, 0), 5)
    p.text(line_item(f"TASKS QUEUED: {task_count}", f"{total_load:>2} LVL"))
    p.text(line_item("COMPLETED TODAY: 1", "STREAK: 3D"))
    p.text(line_item("TOTAL LOAD", diff_ascii(total_bucket)))

    p.text(MAJOR + "\n")

    # ===== QR =====
    p.set(align="center")
    p.text("SCAN TO SYNC / MARK COMPLETE\n")
    p.qr("https://homeassistant.local/dashboard/tasks", size=6)
    p.text("THERMAL://SYNC OK\n")
    p.text(MINOR + "\n")

    # ===== FOOTER (randomized, empathetic) =====
    p.text(random.choice(FOOTERS) + "\n")

    p.cut()
    p.close()

if __name__ == "__main__":
    main()

