from escpos.printer import Network
from datetime import datetime

p = Network("192.168.88.154")

def raw(hexstr):
    p._raw(bytes.fromhex(hexstr))

now = datetime.now()

# Reset
raw("1B 40")

# ===== BIG HEADER =====
raw("1D 21 22")  # 3x3 text
p.text("THERMAL TASK NODE\n")
raw("1D 21 00")

p.text("FASTAF INDUSTRIES :: NODE 01\n")
p.text("TORONTO // SECTOR 416\n")

p.text("-" * 48 + "\n")

# ===== META =====
p.text(f"DATE {now:%Y-%m-%d}".ljust(32))
p.text(f"TIME {now:%H:%M}\n")
p.text("RECEIPT #000021".ljust(32))
p.text("OP ALEX\n")

p.text("-" * 48 + "\n")

# ===== TASKS =====
tasks = [
    ("TAKE OUT RECYCLING", "★★☆"),
    ("WIPE KITCHEN COUNTERS", "★☆☆"),
    ("INBOX ZERO (15 ITEMS)", "★★★"),
]

for name, diff in tasks:
    left = f"[ ] {name}"
    p.text(left.ljust(42))
    p.text(diff + "\n")

p.text("-" * 48 + "\n")

# ===== TOTALS =====
p.text("TASKS QUEUED: 3".ljust(28))
p.text("TOTAL LOAD: ★★★★★★\n")
p.text("COMPLETED TODAY: 1".ljust(28))
p.text("STREAK: 3 DAYS\n")

p.text("-" * 48 + "\n")

# ===== QR PLACEHOLDER =====
p.text("SCAN TO SYNC / MARK COMPLETE\n")
p.qr("https://homeassistant.local/dashboard/tasks", size=6)

p.text("-" * 48 + "\n")
p.text("NO REFUNDS. EXECUTE TASKS IMMEDIATELY.\n")

# Cut
p.cut()
