from escpos.printer import Network

PRINTER_IP = "192.168.88.154"   # <-- your printer IP
PRINTER_PORT = 9100
IMAGE_NO = 3                   # try 0 if this doesn't work

p = Network(PRINTER_IP, PRINTER_PORT, profile="default")

def raw(hexstr: str):
    p._raw(bytes.fromhex(hexstr))

def print_nv_logo(image_no: int):
    # ESC/POS: FS p n m  ->  1C 70 n m
    # n = image number
    # m = mode (0 = normal)
    raw(f"1C 70 {image_no:02X} 00")

def main():
    p.open()

    # Initialize printer
    raw("1B 40")   # ESC @

    # Center (may warn; safe)
    p.set(align="center")

    # Print NV logo
    print_nv_logo(IMAGE_NO)

    # Feed & cut
    p.text("\n\n")
    p.cut()

    p.close()

if __name__ == "__main__":
    main()
