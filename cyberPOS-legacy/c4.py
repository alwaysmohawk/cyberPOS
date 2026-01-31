from escpos.printer import Network
from datetime import datetime
from PIL import Image, ImageChops, ImageOps

# ===== CONFIG =====
PRINTER_IP = "192.168.88.154"     # <-- your printer IP
PRINTER_PORT = 9100
LOGO_PATH = "fastafLogo.png"

# Start conservative; bump to 560 if you want it wider and it doesn't clip
LOGO_TARGET_WIDTH_PX = 520
LOGO_PAD_PX = 10

RECEIPT_NO = 21

# ===== PRINTER =====
p = Network(PRINTER_IP, PRINTER_PORT, profile="default")

def raw(hexstr: str):
    p._raw(bytes.fromhex(hexstr))

def invert(on: bool):
    # GS B n (invert). Common on ESC/POS clones. If unsupported, usually harmless.
    raw("1D 42 01" if on else "1D 42 00")

MAJOR = "=" * 48
MINOR = "-" * 48

def diff_ascii(level: int) -> str:
    # level: 1..3
    return "[" + ("*" * level).ljust(3, ".") + "]"   # [*..] [**.] [***]

def line_item(left: str, right: str) -> str:
    # 48-column line with dot leaders
    right = right.rjust(6)
    max_left = 48 - len(right) - 1
    left = left[:max_left]
    dots = "." * max(1, (48 - len(left) - len(right) - 1))
    return f"{left} {dots}{right}\n"

def prep_logo(path: str, target_width_px: int = 520, pad_px: int = 10) -> Image.Image:
    """
    Prepare logo for thermal printing:
    - flatten transparency to white
    - auto-crop whitespace
    - autocontrast for crispness
    - scale to target width
    - add padding
    - convert to 1-bit (dither)
    """
    img = Image.open(path).convert("RGBA")

    # Flatten alpha to white
    bg = Image.new("RGBA", img.size, (255, 255, 255, 255))
    img = Image.alpha_composite(bg, img).convert("RGB")

    # Auto-crop near-white background
    white_bg = Image.new("RGB", img.size, (255, 255, 255))
    diff = ImageChops.difference(img, white_bg)
    bbox = diff.getbbox()
    if bbox:
        img = img.crop(bbox)

    # Improve contrast slightly
    img = ImageOps.autocontrast(img)

    # Scale to target width
    if img.width != target_width_px:
        new_h = int(img.height * (target_width_px / img.width))
        img = img.resize((target_width_px, new_h), Image.LANCZOS)

    # Add padding so it doesn't kiss the edges
    if pad_px > 0:
        img = ImageOps.expand(img, border=pad_px, fill="white")

    # Convert to 1-bit (dither)
    img = img.convert("1")
    return img

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

    # ===== OPTION B: BLACK BAR / LOGO / BLACK BAR =====
    p.set(align="center")

    invert(True)
    p.text(" " * 48 + "\n")
    invert(False)

    logo = prep_logo(LOGO_PATH, target_width_px=LOGO_TARGET_WIDTH_PX, pad_px=LOGO_PAD_PX)
    p.image(logo)

    invert(True)
    p.text(" " * 48 + "\n")
    invert(False)

    # --- micro breathing room ---
    p.text("\n")

    # ===== HEADER =====
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
    # Bucket to 1..3 for the [*..] style
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
    p.open()
    raw("1B 40")
    print_nv_logo(1)
    p.cut()
    p.close()

if __name__ == "__main__":
    main()
