"""Shared printer helpers for cyberPOS receipts.
Owns the Network connection, ESC/POS control codes, and receipt formatting utilities.
"""

from escpos.printer import Network
from PIL import Image

# ===== CONFIG =====
PRINTER_IP = "192.168.88.154"
PRINTER_PORT = 9100
LOGO_BMP_PATH = "fastaf_nv.bmp"

# ===== CONNECTION =====
p = Network(PRINTER_IP, PRINTER_PORT, profile="default")

def raw(hexstr: str):
    p._raw(bytes.fromhex(hexstr))

def invert(on: bool):
    raw("1D 42 01" if on else "1D 42 00")

# ===== CONSTANTS =====
MAJOR = "=" * 48
MINOR = "-" * 48

# ===== LOGO =====
def print_logo():
    """Print the centered logo with inverted padding bars"""
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

# ===== FORMATTING =====
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
