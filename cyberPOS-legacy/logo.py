from escpos.printer import Network
from datetime import datetime
from PIL import Image

PRINTER_IP = "192.168.88.154"   # <-- your printer IP
PRINTER_PORT = 9100

LOGO_PATH = "fastafLogo.png"    # <-- put this next to the script

p = Network(PRINTER_IP, PRINTER_PORT, profile="default")

def raw(hexstr: str):
    p._raw(bytes.fromhex(hexstr))

def invert(on: bool):
    raw("1D 42 01" if on else "1D 42 00")  # GS B n (common; safe if unsupported)

MAJOR = "=" * 48
MINOR = "-" * 48

def diff_ascii(level: int) -> str:
    return "[" + ("*" * level).ljust(3, ".") + "]"   # [*..] [**.] [***]

def line_item(left: str, right: str) -> str:
    right = right.rjust(6)
    max_left = 48 - len(right) - 1
    left = left[:max_left]
    dots = "." * max(1, (48 - len(left) - len(right) - 1))
    return f"{left} {dots}{right}\n"

def prep_logo(path: str, max_width_px: int = 560) -> Image.Image:
    """
    Prepares a logo for thermal printing:
    - scales down to max_width_px (keep aspect)
    - converts to 1-bit with Floyd-Steinberg dithering
    """
    img = Image.open(path).convert("RGBA")

    # Put logo on white background (avoid transparent weirdness)
    bg = Image.new("RGBA", img.size, (255, 255, 255, 255))
    img = Image.alpha_composite(bg, img).convert("RGB")

    # Resize to fit width
    if img.width > max_width_px:
        new_h = int(img.height * (max_width_px / img.width))
        img = img.resize((max_width_px, new_h), Image.LANCZOS)

    # Convert to 1-bit with dithering for nicer gradients/edges
    img = img.convert("1")  # Pillow uses dithering by default here (FS)

    return img

def main():
    now = datetime.now()
    receipt_no = 21

    tasks = [
        ("TAKE OUT RECYCLING", 2),
        ("WIPE KITCHEN COUNTERS", 1),
        ("INBOX ZERO (15 ITEMS)", 3),
    ]
    total_load = sum(lvl for _, lvl in tasks)

    p.open()
    raw("1B 40")  # init
    p.set(align="center")

    # ===== LOGO =====
    # For 80mm printers, printable width is often 576 dots.
    # 560 is a safe width that avoids edge clipping on many models.
    logo = prep_logo(LOGO_PATH, max_width_px=560)
    p.image(logo)
    p.text("\n")

    # ===== TERMINAL HEADER =====
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

    p.text("NO REFUNDS. EXECUTE TASKS IMMEDIATELY.\n")

    p.cut()
    p.close()

if __name__ == "__main__":
    main()
