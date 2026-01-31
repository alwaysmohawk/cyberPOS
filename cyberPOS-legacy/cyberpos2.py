from escpos.printer import Network
from datetime import datetime

PRINTER_IP = "192.168.88.154"   # <-- your printer
PRINTER_PORT = 9100

p = Network(PRINTER_IP, PRINTER_PORT, profile="default")

def raw(hexstr: str):
    p._raw(bytes.fromhex(hexstr))

def diff_ascii(level: int) -> str:
    # level: 1..3
    return "[" + ("*" * level).ljust(3, ".") + "]"   # [*..] [**.] [***]

def main():
    now = datetime.now()
    tasks = [
        ("TAKE OUT RECYCLING", 2),
        ("WIPE KITCHEN COUNTERS", 1),
        ("INBOX ZERO (15 ITEMS)", 3),
    ]

    total_load = sum(lvl for _, lvl in tasks)

    p.open()
    raw("1B 40")              # init
    p.set(align="center")

    # ===== HEADER (2x2 so it doesn't wrap) =====
    raw("1D 21 11")           # 2x2
    p.text("THERMAL TASK NODE\n")
    raw("1D 21 00")

    p.text("FASTAF INDUSTRIES :: NODE 01\n")
    p.text("TORONTO // SECTOR 416\n")
    p.text("-" * 48 + "\n")

    # ===== META =====
    p.set(align="left")
    p.text(f"DATE {now:%Y-%m-%d}".ljust(32) + f"TIME {now:%H:%M}\n")
    p.text("RECEIPT #000021".ljust(32) + "OP ALEXANDER\n")
    p.text("-" * 48 + "\n")

    # ===== TASKS =====
    for name, lvl in tasks:
        left = f"[ ] {name}"
        right = diff_ascii(lvl)
        p.text(left[:36].ljust(36) + right.rjust(12) + "\n")

    p.text("-" * 48 + "\n")

    # ===== TOTALS =====
    p.text("TASKS QUEUED: 3".ljust(28) + f"TOTAL LOAD: {diff_ascii(min(total_load,3))}\n")
    p.text("COMPLETED TODAY: 1".ljust(28) + "STREAK: 3 DAYS\n")
    p.text("-" * 48 + "\n")

    # ===== QR =====
    p.set(align="center")
    p.text("SCAN TO SYNC / MARK COMPLETE\n")
    p.qr("https://homeassistant.local/dashboard/tasks", size=6)

    p.text("-" * 48 + "\n")
    p.text("NO REFUNDS. EXECUTE TASKS IMMEDIATELY.\n")

    p.cut()
    p.close()

if __name__ == "__main__":
    main()
