"""
cyberPOS on-demand receipts for the console: task cards, notes, checklists,
printer status and "run a dispatch now".
"""

import socket
import subprocess
import textwrap
import threading
from datetime import datetime

from printer import p, raw, invert, MAJOR, MINOR, PRINTER_IP, PRINTER_PORT, print_logo
from onePer import print_task_receipt

DISPATCHES = {
    "morning": "cyberpos-morning.service",
    "evening": "cyberpos-evening.service",
    "night": "cyberpos-night.service",
}

_lock = threading.Lock()


def printer_online(timeout=2):
    try:
        with socket.create_connection((PRINTER_IP, PRINTER_PORT), timeout=timeout):
            return True
    except OSError:
        return False


def _header(title):
    raw("1B 40")  # ESC @ init
    p.set(align="center")
    raw("1D 21 11")  # 2x2
    p.text(f"{title}\n")
    raw("1D 21 00")
    p.text("fastAF industries :: NODE 01\n")
    p.text(MAJOR + "\n")
    p.set(align="left")
    now = datetime.now()
    p.text(f"DATE {now:%Y-%m-%d}".ljust(32) + f"TIME {now:%H:%M}\n")
    p.text(MINOR + "\n")


def print_task_card(task):
    """One task card with a completion QR (same layout as onePer.py)"""
    with _lock:
        p.open()
        try:
            print_task_receipt(task["title"], task["difficulty"], 100, 1, 1, task["id"], task["list_id"])
        finally:
            p.close()


def print_note(text, title="NOTE"):
    with _lock:
        p.open()
        try:
            _header(title)
            for para in text.splitlines() or [""]:
                for line in textwrap.wrap(para, 48) or [""]:
                    p.text(line + "\n")
            p.text(MAJOR + "\n")
            p.cut()
        finally:
            p.close()


def print_checklist(title, items, logo=False):
    """items: list of strings (or (left, right) tuples) printed with [ ] boxes"""
    with _lock:
        p.open()
        try:
            if logo:
                raw("1B 40")
                print_logo()
            _header(title)
            for item in items:
                if isinstance(item, tuple):
                    left, right = item
                    width = 47 - len(right)
                    p.text(f"[ ] {left}"[:width].ljust(width) + " " + right + "\n")
                else:
                    lines = textwrap.wrap(item, 44) or [""]
                    p.text(f"[ ] {lines[0]}\n")
                    for line in lines[1:]:
                        p.text(f"    {line}\n")
            p.text(MAJOR + "\n")
            p.set(align="center")
            invert(True)
            p.text(" ONE AT A TIME. ".center(48) + "\n")
            invert(False)
            p.cut()
        finally:
            p.close()


def run_dispatch(name):
    """Start a dispatch through systemd so it logs and reports like the scheduled runs"""
    unit = DISPATCHES[name]
    subprocess.run(["systemctl", "start", "--no-block", unit], check=True, timeout=10)


def dispatch_status():
    """{name: {"result": "success"|"exit-code"|..., "last": "YYYY-MM-DD HH:MM" or ""}}"""
    out = {}
    for name, unit in DISPATCHES.items():
        try:
            res = subprocess.run(
                ["systemctl", "show", unit, "-p", "Result", "-p", "ExecMainExitTimestamp",
                 "-p", "ActiveState", "-p", "InvocationID"],
                capture_output=True, text=True, timeout=5).stdout
            props = dict(line.split("=", 1) for line in res.strip().splitlines() if "=" in line)
        except Exception:
            props = {}
        last = props.get("ExecMainExitTimestamp", "")
        out[name] = {
            "result": props.get("Result", "unknown"),
            "active": props.get("ActiveState", ""),
            "last": " ".join(last.split()[1:3])[:16] if last else "",
            "invocation": props.get("InvocationID", ""),
        }
    return out
