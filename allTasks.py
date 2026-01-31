from datetime import datetime
import random
from google_tasks_helper import get_tasks_for_printer
from printer import p, raw, invert, MAJOR, MINOR, print_logo, diff_ascii, line_item

# ===== CONFIG =====
RECEIPT_NO = 21
MAX_TASKS = 10  # Maximum number of tasks to print

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
    "YOU'RE MAKING PROGRESS. KEEP GOING.",
    "ONE STEP IS STILL A STEP.",
    "SMALL WINS ADD UP.",
    "STEADY BEATS FAST.",
    "KEEP GOING. YOU'RE ON TRACK.",
    "THANK YOU FOR TAKING THIS ON.",
    "YOU'VE GOT THIS.",

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

    # ===== HEADER =====
    print_logo()

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
