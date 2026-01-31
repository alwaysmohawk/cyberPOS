from escpos.printer import Network
import time

PRINTER_IP = "192.168.88.154"
PRINTER_PORT = 9100

p = Network(PRINTER_IP, PRINTER_PORT, profile="default")

def raw(hexstr: str):
    p._raw(bytes.fromhex(hexstr))

def section(title: str):
    p.text("\n" * 2)
    p.text("=" * 48 + "\n")
    p.text(title + "\n")
    p.text("=" * 48 + "\n")
    p.text("\n")

def main():
    p.open()
    raw("1B 40")  # ESC @ init
    p.set(align="left")

    # --------------------------------------------------
    section("METHOD 1: BEL (0x07)")
    p.text("Sending ASCII BEL (0x07)\n")
    p.text("If supported, you should hear a beep now.\n\n")
    p._raw(b"\x07")
    time.sleep(1)

    # --------------------------------------------------
    section("METHOD 2: python-escpos buzzer()")
    p.text("Using p.buzzer(times=1, duration=2)\n")
    p.text("If supported, you should hear a short beep.\n\n")
    try:
        p.buzzer(times=1, duration=2)
    except Exception as e:
        p.text(f"buzzer() exception: {e}\n")
    time.sleep(1)

    # --------------------------------------------------
    section("METHOD 3: ESC ( A — Epson beeper fn=48")
    p.text("ESC ( A  fn=48  (official Epson command)\n")
    p.text("Some clones support this.\n\n")
    # 1B 28 41 04 00 30 37 02 05
    raw("1B 28 41 04 00 30 37 02 05")
    time.sleep(1)

    # --------------------------------------------------
    section("METHOD 4: ESC B (legacy bell)")
    p.text("ESC B n t  (very old / rare)\n")
    p.text("n=2 times, t=3 duration\n\n")
    # ESC B 02 03
    raw("1B 42 02 03")
    time.sleep(1)

    # --------------------------------------------------
    section("METHOD 5: GS a  (non-standard test)")
    p.text("GS a 07 (rare / vendor-specific)\n\n")
    raw("1D 61 07")
    time.sleep(1)

    # --------------------------------------------------
    section("END OF BEEP TEST")
    p.text("If you heard nothing, ESC/POS beeper\n")
    p.text("is not exposed to print-time commands.\n")

    p.cut()
    p.close()

if __name__ == "__main__":
    main()
