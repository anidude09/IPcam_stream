import csv
from datetime import datetime
import serial

# ====== CONFIG ======
# On  Mac, AWR300 serial device is:
SERIAL_PORT = "/dev/tty.usbmodemAWR300_0100A1"
BAUDRATE = 9600          # AWR300 default for RS232/CDC
CSV_FILE = "cattle_log.csv"
# ====================

def open_serial(port, baudrate=9600, timeout=1.0):
    """Open the serial port to the AWR300."""
    return serial.Serial(port=port, baudrate=baudrate, timeout=timeout)

def main():
    group_name = input("Enter group name for this session (e.g. Weighing_2024_12_01): ").strip()
    if not group_name:
        group_name = "default"

    try:
        with open(CSV_FILE, "r", newline="") as f:
            file_exists = True
    except FileNotFoundError:
        file_exists = False

    # Open CSV for appending
    f = open(CSV_FILE, "a", newline="")
    writer = csv.writer(f)

    if not file_exists:
        writer.writerow(["eid", "timestamp", "date", "time", "group"])

    print(f"\nOpening serial port {SERIAL_PORT} at {BAUDRATE} baud...")
    ser = open_serial(SERIAL_PORT, BAUDRATE)

    print(f"Logging to {CSV_FILE}")
    print(f"Group name: {group_name}")
    print("Scan tags with the AWR300. Press Ctrl+C to stop.\n")

    try:
        while True:
            line = ser.readline()
            if not line:
                continue  # timeout, nothing read

            # Decode ASCII text and strip CR/LF
            text = line.decode("ascii", errors="ignore").strip()

            if not text:
                continue

            # Basic sanity check: EID should be mostly digits
            eid = text

            now = datetime.now()
            iso_ts = now.isoformat(timespec="seconds")
            date_str = now.date().isoformat()
            time_str = now.time().strftime("%H:%M:%S")

            writer.writerow([eid, iso_ts, date_str, time_str, group_name])
            f.flush()

            print(f"Read EID: {eid} @ {iso_ts} (group={group_name})")

    except KeyboardInterrupt:
        print("\nStopping logger...")
    finally:
        try:
            ser.close()
        except Exception:
            pass
        try:
            f.close()
        except Exception:
            pass

if __name__ == "__main__":
    main()
