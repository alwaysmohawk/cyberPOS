from escpos.printer import Network
from datetime import datetime
from PIL import Image

# ===== CONFIG =====
PRINTER_IP = "192.168.88.154"
PRINTER_PORT = 9100
LOGO_BMP_PATH = "fastaf_nv.bmp"

RECEIPT_NO = 21

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
    # Difficulty indicator: [*..] [**.] [***]
    return "[" + ("*" * level).ljust(3, ".") + "]"

def line_item(left: str, right: str) -> str:
    # Dot-leader line to 48 columns
    right = right.rjust(6)
    max_left = 48 - len(right) - 1
    left = left[:max_left]
    dots = "." * max(1, (48 - len(left) - len(right) - 1))
    return f"{left} {dots}{right}\n"

def main():
    now = datetime.now()

    tasks = [
        ("TAKE OUT RECYCLING", 2),
        ("WIPE KITCHEN COUNTERS", 1),
        ("INBOX ZERO (15 ITEMS)", 3),
    ]
    total_load = sum(lvl for _, lvl in tasks)

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

    # Full spacer line (your preferred padding)
    p.text("\n")

    # ===== TITLE =====
    raw("1D 21 11")  # 2x2
    p.text("THERMAL TASK NODE\n")
    raw("1D 21 00")

    p.text("FASTAF INDUSTRIES :: NODE 01\n")
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
    total_bucket = min(max(total_load, 1), 3)
    p.text(line_item("TASKS QUEUED: 3", f"{total_load:>2} LVL"))
    p.text(line_item("COMPLETED TODAY: 1", "STREAK: 3D"))
    p.text(line_item("TOTAL LOAD", diff_ascii(total_bucket)))

    p.text(MAJOR + "\n")

    # ===== QR =====
    p.set(align="center")
    p.text("SCAN TO SYNC / MARK COMPLETE\n")
    p.qr("https://homeassistant.local/dashboard/tasks", size=6)
    p.text("THERMAL://SYNC OK\n")
    p.text(MINOR + "\n")

    # ===== FOOTER =====
    p.text("NO REFUNDS. EXECUTE TASKS IMMEDIATELY.\n")

    p.cut()
    p.close()

if __name__ == "__main__":
    main()
