from escpos.printer import Network

PRINTER_IP = "192.168.88.154"
PRINTER_PORT = 9100

p = Network(PRINTER_IP, PRINTER_PORT, profile="default")

def main():
    p.open()
    p._raw(b"\x1b\x40")  # ESC @ init

    # Structured beeper command (safe if unsupported)
    try:
        p.buzzer(times=1, duration=2)
    except Exception as e:
        print("Buzzer not supported:", e)

    p.text("BEEP TEST\n")
    p.cut()
    p.close()

if __name__ == "__main__":
    main()
