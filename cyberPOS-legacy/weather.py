from escpos.printer import Network
import datetime

printer_ip = "192.168.88.154"

def print_briefing():
    try:
        # Use 'default' instead of 'generic'
        p = Network(printer_ip, profile="default")

        # --- 1. HEADER (Raw Hex for Double Height/Width) ---
        p.set(align='center')
        p._raw(b'\x1d\x21\x11') # Big text mode
        p.text("MONDAY BRIEFING\n")
        p._raw(b'\x1d\x21\x00') # Reset to normal
        p.text(f"{datetime.datetime.now().strftime('%b %d, %Y')}\n")
        p.text("================================\n")

        # --- 2. TORONTO WEATHER SECTION ---
        p.set(align='left', bold=True)
        p.text("WEATHER (Toronto):\n")
        p.set(bold=False)
        # Placeholder for your weather data
        p.text("- Temp: -2 C (Feels like -7)\n")
        p.text("- Condition: Light Snow\n")
        p.text("- Commute: DVP/Gardiner clear\n\n")

        # --- 3. THE "LAB" TO-DO LIST ---
        # Using Font B for a compact list
        p.set(bold=True)
        p.text("GARAGE & LAB TASKS:\n")
        p.set(bold=False, font='b')
        tasks = [
            "[ ] Check STI brake fluid levels",
            "[ ] Order Jeep XJ headliner clips",
            "[ ] Clear Proxmox 'pinkzpool' logs",
            "[ ] Calibration cube on Voron",
            "[ ] Burnish edges on leather belt"
        ]
        for task in tasks:
            p.text(f"{task}\n")
        
        # --- 4. QR CODE (Quick link to your Proxmox dashboard) ---
        p.set(align='center', font='a')
        p.text("\nSYSTEM STATUS\n")
        p.qr("http://192.168.88.114:8006", size=6) # Your Proxmox IP

        # --- 5. FOOTER ---
        p.text("\n" + ("-" * 32) + "\n")
        p.text("Done is better than perfect.\n")
        
        p.cut()
        print("Toronto Morning Briefing printed!")

    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    print_briefing()
