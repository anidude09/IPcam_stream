import cv2
import time
import os
import threading
import sys
from requests.exceptions import RequestException

# --- Import functions and config from our existing API test script ---
# This is a clean way to re-use our code
try:
    from temperature_api_test import get_dot_temp, IP_ADDRESS, USERNAME, PASSWORD, THERMAL_CHANNEL
except ImportError:
    print("Error: Could not import from 'temperature_api_test.py'.")
    print("Please make sure 'temperature_api_test.py' is in the same directory.")
    sys.exit(1)

# --- Configuration ---
THERMAL_PROFILE = "profile4"  # profile4 is the thermal stream
RTSP_URL = f"rtsp://{USERNAME}:{PASSWORD}@{IP_ADDRESS}:554/{THERMAL_PROFILE}"
WINDOW_NAME = "Thermal Stream - Click for Temp, 'q' to Quit"

# --- Shared State ---
# This dictionary will be shared between the main thread and the temp thread
# We set a default coordinate from your document's example
shared_state = {
    "target_x": 192,
    "target_y": 144,
    "current_temp_c": None,
    "status_message": "Click to measure temperature...",
    "running": True  # Flag to signal threads to stop
}


# --- Mouse Click Callback ---
def mouse_callback(event, x, y, flags, param):
    """
    This function is called by OpenCV whenever a mouse event happens
    in our main window.
    """
    if event == cv2.EVENT_LBUTTONDOWN:
        # User clicked the left mouse button
        print(f"New target set at: ({x}, {y})")
        shared_state["target_x"] = x
        shared_state["target_y"] = y
        shared_state["current_temp_c"] = None  # Reset temp
        shared_state["status_message"] = "Fetching temp..."


# --- Temperature Fetcher Thread ---
def temperature_fetcher_thread():
    """
    A dedicated thread that continuously fetches the temperature
    for the target (x, y) coordinates.

    This runs in the background so it doesn't lag the video feed,
    as HTTP requests are much slower than video frames.
    """
    print("Temperature fetcher thread started.")
    last_fetched_x = -1
    last_fetched_y = -1

    while shared_state["running"]:
        x = shared_state["target_x"]
        y = shared_state["target_y"]

        # Only fetch if the target has changed
        if x != last_fetched_x or y != last_fetched_y:
            try:
                # Call the function from our other script
                temp_c = get_dot_temp(x, y, THERMAL_CHANNEL)

                if temp_c is not None:
                    shared_state["current_temp_c"] = temp_c
                    shared_state["status_message"] = f"{temp_c} C"
                else:
                    shared_state["status_message"] = "Failed to get temp"

                last_fetched_x = x
                last_fetched_y = y

            except RequestException as e:
                print(f"Temp Fetch Error: {e}")
                shared_state["status_message"] = "Connection Error"
                # Wait a bit before retrying a connection error
                time.sleep(2.0)
            except Exception as e:
                print(f"Unknown error in temp thread: {e}")
                shared_state["status_message"] = "Error"
                time.sleep(2.0)

        # Wait a short time before checking for a new target
        time.sleep(0.5)

    print("Temperature fetcher thread stopping.")


# --- Main Application Logic ---
def main():
    # Set the RTSP transport to TCP
    os.environ["OPENCV_FFMPEG_CAPTURE_OPTIONS"] = "rtsp_transport;tcp"

    print(f"Attempting to connect to thermal stream: {RTSP_URL}")
    cap = cv2.VideoCapture(RTSP_URL, cv2.CAP_FFMPEG)

    if not cap.isOpened():
        print("Error: Cannot open RTSP stream.")
        return

    print("Successfully opened stream.")

    # Create the OpenCV window and set its mouse callback
    cv2.namedWindow(WINDOW_NAME)
    cv2.setMouseCallback(WINDOW_NAME, mouse_callback)

    # Start the temperature fetcher thread
    t = threading.Thread(target=temperature_fetcher_thread, daemon=True)
    t.start()

    try:
        while True:
            ok, frame = cap.read()
            if not ok:
                print("Error: Cannot read frame. Stream may have ended.")
                break

            # Get the current state
            x = shared_state["target_x"]
            y = shared_state["target_y"]
            message = shared_state["status_message"]

            # --- Draw graphics on the frame ---

            # 1. Draw the target crosshairs
            cv2.circle(frame, (x, y), 7, (0, 255, 0), 2)  # Green circle
            cv2.line(frame, (x - 15, y), (x + 15, y), (0, 255, 0), 1)
            cv2.line(frame, (x, y - 15), (x, y + 15), (0, 255, 0), 1)

            # 2. Draw the temperature text
            # Add a semi-transparent background box for readability
            (text_w, text_h), _ = cv2.getTextSize(message, cv2.FONT_HERSHEY_SIMPLEX, 0.7, 2)
            box_coords = ((x + 10, y - 10 - text_h), (x + 20 + text_w, y))
            overlay = frame.copy()
            cv2.rectangle(overlay, box_coords[0], box_coords[1], (0, 0, 0), -1)
            alpha = 0.6  # Transparency
            frame = cv2.addWeighted(overlay, alpha, frame, 1 - alpha, 0)

            # Put the text on top
            cv2.putText(frame, message, (x + 15, y - 10),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 255), 2)

            # Display the resulting frame
            cv2.imshow(WINDOW_NAME, frame)

            # Wait for 1ms and check if 'q' key was pressed
            if cv2.waitKey(1) & 0xFF == ord('q'):
                print("'q' key pressed. Exiting...")
                break

    finally:
        # --- Cleanup ---
        print("Cleaning up...")
        shared_state["running"] = False  # Signal thread to stop
        t.join(timeout=2.0)  # Wait for thread
        cap.release()
        cv2.destroyAllWindows()
        print("Stream closed.")


if __name__ == "__main__":
    main()