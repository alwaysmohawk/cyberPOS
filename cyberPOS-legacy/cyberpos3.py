from escpos.printer import Network
from datetime import datetime

PRINTER_IP = "192.168.88.154"   # <-- your printer IP
PRINTER_PORT = 9100

p = Network(PRINTER_IP, PRINTER_PORT, profile="default")

def raw(hexstr: str):
    p._raw(bytes.fromhex(hexstr))

# Try inverse mode (many ESC/POS printers support this)
# GS B n : 1D 42 n  (n=1 invert on, n=0 off)
def invert(on: bool):
    raw("1D 42 01" if on else "1D 42 00")

MAJOR = "=" * 48
MINOR = "-" * 48

def diff_ascii(level: int) -> str:
    return "[" + ("*" * level).ljust(3, ".") + "]"   # [*..] [**.] [***]

def line_item(left: str, right: str) -> str:
    # Dot-leader line to 48 cols
    # Keep right fixed-width, fill middle with dots.
    right = right.rjust(6)  # fits like " [**.]" etc
    max_left = 48 - len(right) - 1
    left = left[:max_left]
    dots = "." * max(1, (48 - len(left) - len(right) - 1))
    return f"{left} {dots}{right}\n"

def main():
    now = datetime.now()
    receipt_no = 21  # later we can make this persistent

    tasks = [
        ("TAKE OUT RECYCLING", 2),
        ("WIPE KITCHEN COUNTERS", 1),
        ("INBOX ZERO (15 ITEMS)", 3),
    ]
    total_load = sum(lvl for _, lvl in tasks)

    p.open()
    raw("1B 40")  # init
    p.set(align="center")

    # ===== TERMINAL HEADER =====
    # Black bar (safe: if inverse not supported, it just prints normal text)
    invert(True)
    p.text(" " * 48 + "\n")
    invert(False)

    raw("1D 21 11")  # 2x2
    p.text("THERMAL TASK NODE\n")
    raw("1D 21 00")

    p.text("FASTAF INDUSTRIES :: NODE 01\n")
    p.text("TORONTO // SECTOR 416\n")
    p.text(MAJOR + "\n")

    # ===== META =====
    p.set(align="left")
    p.text(f"DATE {now:%Y-%m-%d}".ljust(32) + f"TIME {now:%H:%M}\n")
    p.text(f"RECEIPT #{receipt_no:06d}".ljust(32) + "OP ALEXANDER\n")
    p.text(MINOR + "\n")

    # ===== TASKS =====
    for name, lvl in tasks:
        p.text(line_item(f"[ ] {name}", diff_ascii(lvl)))

    p.text(MAJOR + "\n")

    # ===== TOTALS =====
    # Map total load to 1..3 for now (we can later do [******] style)
    total_bucket = min(max(total_load, 1), 3)
    p.text(line_item("TASKS QUEUED: 3", f"{total_load:>2} LVL"))
    p.
