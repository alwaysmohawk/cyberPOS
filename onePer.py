from escpos.printer import Network
from datetime import datetime
from PIL import Image
import random
import urllib.parse
from google_tasks_helper import get_tasks_with_ids

# ===== CONFIG =====
PRINTER_IP = "192.168.88.154"
PRINTER_PORT = 9100
LOGO_BMP_PATH = "fastaf_nv.bmp"

RECEIPT_NO_START = 100  # Starting receipt number for individual tasks
MAX_TASKS = 10  # Maximum number of tasks to fetch

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

    # --- Single task focused ---
    "ONE TASK AT A TIME.",
    "FOCUS. EXECUTE. COMPLETE.",
    "THIS IS YOUR ONLY JOB RIGHT NOW.",
    "SINGULAR FOCUS. MAXIMUM IMPACT.",
]

def print_task_receipt(task_name: str, difficulty: int, receipt_no: int, task_num: int, total_tasks: int, task_id: str = "", tasklist_id: str = ""):
    """Print a single task on its own receipt"""

    now = datetime.now()

    raw("1B 40")  # ESC @ init

    # ===== HEADER =====
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

    # ===== TITLE =====
    raw("1D 21 11")  # 2x2
    p.text("TASK CARD\n")
    raw("1D 21 00")

    p.text("fastAF industries :: NODE 01\n")
    p.text("TORONTO // SECTOR 416\n")
    p.text(MAJOR + "\n")

    # ===== META =====
    p.set(align="left")
    p.text(f"DATE {now:%Y-%m-%d}".ljust(32) + f"TIME {now:%H:%M}\n")
    p.text(f"CARD #{receipt_no:06d}".ljust(32) + "OP ALEXANDER\n")
    p.text(f"TASK {task_num} OF {total_tasks}".ljust(32) + f"LOAD {diff_ascii(difficulty)}\n")
    p.text(MINOR + "\n")

    # ===== TASK =====
    p.set(align="left")
    p.text("\n")

    # Wrap long task names across multiple lines
    max_width = 35  # Leave room for difficulty indicator
    if len(task_name) > max_width:
        words = task_name.split()
        lines = []
        current_line = ""
        for word in words:
            if len(current_line) + len(word) + 1 <= max_width:
                current_line += (word + " ")
            else:
                if current_line:
                    lines.append(current_line.strip())
                current_line = word + " "
        if current_line:
            lines.append(current_line.strip())

        # Print first line with difficulty indicator
        p.text(line_item(f"[ ] {lines[0]}", diff_ascii(difficulty)))
        # Print remaining lines without difficulty indicator
        for line in lines[1:]:
            p.text(f"    {line}\n")
    else:
        p.text(line_item(f"[ ] {task_name}", diff_ascii(difficulty)))

    p.text("\n")
    p.text(MINOR + "\n")

    # ===== TASK INFO =====
    difficulty_text = ["TRIVIAL", "VERY LIGHT", "LIGHT", "MODERATE", "HEAVY", "VERY HEAVY"]
    est_time = ["<5 MIN", "5-10 MIN", "10-20 MIN", "20-45 MIN", "45-90 MIN", "90+ MIN"]

    p.text(line_item("DIFFICULTY", difficulty_text[difficulty]))
    p.text(line_item("EST. TIME", est_time[difficulty]))
    p.text(MAJOR + "\n")

    # ===== QR =====
    p.set(align="center")
    p.text("SCAN TO MARK COMPLETE\n")

    # Generate completion URL with task info
    if task_id and tasklist_id:
        # URL encode the task name for the query parameter
        task_name_encoded = urllib.parse.quote(task_name)
        completion_url = f"http://192.168.88.130:5000/complete/{tasklist_id}/{task_id}?name={task_name_encoded}"
        p.qr(completion_url, size=6)
    else:
        # Fallback if no task ID
        p.qr("http://192.168.88.130:5000", size=6)

    p.text("THERMAL://SYNC OK\n")
    p.text(MINOR + "\n")

    # ===== FOOTER (randomized, empathetic) =====
    p.text(random.choice(FOOTERS) + "\n")

    p.cut()

def main():
    # Fetch tasks from Google Tasks with IDs
    print("Fetching tasks from Google Tasks...")
    tasks = get_tasks_with_ids(max_results=MAX_TASKS)

    # Fallback to sample tasks if no tasks found
    if not tasks:
        print("No tasks found in Google Tasks. Using sample task.")
        tasks = [
            ("", "", "NO TASKS FOUND - ADD SOME!", 1),  # (task_id, tasklist_id, title, difficulty)
        ]

    total_tasks = len(tasks)
    print(f"\nPrinting {total_tasks} individual task receipts...\n")

    # Open printer connection once
    p.open()

    try:
        # Print each task on its own receipt
        for idx, task_data in enumerate(tasks, start=1):
            # Unpack task data
            if len(task_data) == 4:
                task_id, tasklist_id, task_name, difficulty = task_data
            else:
                # Fallback for old format
                task_id, tasklist_id = "", ""
                task_name, difficulty = task_data[0], task_data[1]

            receipt_no = RECEIPT_NO_START + idx
            print(f"  [{idx}/{total_tasks}] Printing: {task_name[:40]}...")
            print_task_receipt(task_name, difficulty, receipt_no, idx, total_tasks, task_id, tasklist_id)
            print(f"      ✓ Receipt #{receipt_no} complete")

        print(f"\n✓ All {total_tasks} task cards printed successfully!")
    finally:
        # Always close the connection
        p.close()

if __name__ == "__main__":
    main()
