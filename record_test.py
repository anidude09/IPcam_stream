import cv2
import time
import os
import threading
import sys
import queue  # <-- Import queue for thread-safe communication
from datetime import datetime

# --- Configuration ---
# !! IMPORTANT: Update these values based on your camera's setup
IP_ADDRESS = "192.168.0.10"
USERNAME = "admin"
PASSWORD = "admin123"  # Replace with your actual password

# As per your document: profile1=RGB, profile4=Thermal
RGB_PROFILE = "profile1"
THERMAL_PROFILE = "profile4"

# RTSP streams often report an FPS of 0. We need reliable defaults.
# Check your camera's web interface for the stream's actual FPS.
RGB_FPS = 30.0  # User specified 30 FPS for RGB
THERMAL_FPS = 15.0  # Thermal is often lower (e.g., 9, 15, 25). Please verify this!

# Codec for output. 'XVID' is widely compatible and creates .avi files.
FOURCC_CODEC = 'XVID'



# --- End Configuration ---


class StreamCaptureThread(threading.Thread):
    """
    A class to capture a single RTSP stream in its own thread
    and put frames into a queue.
    """

    def __init__(self, rtsp_url, frame_queue, stream_name):
        super().__init__()
        self.rtsp_url = rtsp_url
        self.frame_queue = frame_queue
        self.stream_name = stream_name
        self.running = True  # Flag to control the thread loop
        self.cap = None

        # Force TCP transport for reliability.
        os.environ["OPENCV_FFMPEG_CAPTURE_OPTIONS"] = "rtsp_transport;tcp"
        print(f"[{self.stream_name}] Set 'OPENCV_FFMPEG_CAPTURE_OPTIONS=rtsp_transport;tcp'")

    def run(self):
        """The main logic of the thread."""
        try:
            print(f"[{self.stream_name}] Thread started. Connecting to {self.rtsp_url}...")
            self.cap = cv2.VideoCapture(self.rtsp_url, cv2.CAP_FFMPEG)

            if not self.cap.isOpened():
                print(f"Error: [{self.stream_name}] Cannot open RTSP stream.")
                return

            print(f"[{self.stream_name}] Stream opened successfully.")

            while self.running:
                ok, frame = self.cap.read()

                if not ok:
                    print(f"Error: [{self.stream_name}] Cannot read frame. Stream may have ended.")
                    break

                # If queue is full, drop the oldest frame to add the new one
                if self.frame_queue.full():
                    try:
                        self.frame_queue.get_nowait()  # Discard oldest frame
                    except queue.Empty:
                        pass  # Should not happen, but good to be safe

                # Put the new frame in the queue
                self.frame_queue.put(frame)

        except Exception as e:
            print(f"Error in thread [{self.stream_name}]: {e}")
        finally:
            # Cleanup
            if self.cap:
                self.cap.release()
            print(f"[{self.stream_name}] Capture thread stopped and resources released.")

    def stop(self):
        """Signals the thread to stop."""
        print(f"[{self.stream_name}] Stop signal received.")
        self.running = False


def create_video_writer(filename, fourcc, fps, width, height):
    """Helper function to create a new VideoWriter object."""
    return cv2.VideoWriter(filename, fourcc, fps, (width, height))


# --- Main execution block ---
if __name__ == "__main__":
    # Construct the RTSP URLs
    auth = f"{USERNAME}:{PASSWORD}@"
    base_url = f"rtsp://{auth}{IP_ADDRESS}:554/"

    rgb_rtsp_url = f"{base_url}{RGB_PROFILE}"
    thermal_rtsp_url = f"{base_url}{THERMAL_PROFILE}"

    # Create thread-safe queues to hold frames
    # maxsize=2 means we only buffer 2 frames, prioritizing liveness
    rgb_queue = queue.Queue(maxsize=2)
    thermal_queue = queue.Queue(maxsize=2)

    # Create and start the capture threads
    rgb_thread = StreamCaptureThread(rgb_rtsp_url, rgb_queue, "RGB")
    thermal_thread = StreamCaptureThread(thermal_rtsp_url, thermal_queue, "Thermal")

    rgb_thread.start()
    thermal_thread.start()

    print("\n--- Interactive Dual Stream Viewer & Recorder ---")
    print("Press 'r' to Start/Stop recording.")
    print("Press 'q' to Quit.")
    print("--------------------------------------------------\n")

    last_rgb_frame = None
    last_thermal_frame = None

    is_recording = False
    rgb_writer = None
    thermal_writer = None
    fourcc = cv2.VideoWriter_fourcc(*FOURCC_CODEC)

    try:
        while True:
            # --- Get Frames from Queues ---
            try:
                # Get frames without blocking.
                last_rgb_frame = rgb_queue.get_nowait()
            except queue.Empty:
                pass  # Use the last available frame

            try:
                last_thermal_frame = thermal_queue.get_nowait()
            except queue.Empty:
                pass  # Use the last available frame

            # --- Display Frames ---
            if last_rgb_frame is not None:
                display_rgb = last_rgb_frame.copy()  # Copy to draw on
                if is_recording:
                    # Draw a red recording dot
                    cv2.circle(display_rgb, (30, 30), 15, (0, 0, 255), -1)
                cv2.imshow("RGB Stream (Press 'r' to record, 'q' to quit)", display_rgb)

            if last_thermal_frame is not None:
                display_thermal = last_thermal_frame.copy()  # Copy to draw on
                if is_recording:
                    # Draw a red recording dot
                    cv2.circle(display_thermal, (30, 30), 15, (0, 0, 255), -1)
                cv2.imshow("Thermal Stream (Press 'r' to record, 'q' to quit)", display_thermal)

            # --- Handle User Input ---
            key = cv2.waitKey(1) & 0xFF

            if key == ord('q'):
                print("'q' pressed. Quitting...")
                break

            if key == ord('r'):
                is_recording = not is_recording

                if is_recording:
                    # --- Start Recording ---
                    print("--- STARTING RECORDING ---")
                    # Create timestamped filenames
                    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                    rgb_filename = f"rgb_{timestamp}.avi"
                    thermal_filename = f"thermal_{timestamp}.avi"

                    # Get frame dimensions (we MUST have frames to do this)
                    if last_rgb_frame is not None and last_thermal_frame is not None:
                        h_rgb, w_rgb, _ = last_rgb_frame.shape
                        h_therm, w_therm, _ = last_thermal_frame.shape

                        rgb_writer = create_video_writer(rgb_filename, fourcc, RGB_FPS, w_rgb, h_rgb)
                        thermal_writer = create_video_writer(thermal_filename, fourcc, THERMAL_FPS, w_therm, h_therm)
                        print(f"Recording RGB to: {rgb_filename} at {RGB_FPS} FPS")
                        print(f"Recording Thermal to: {thermal_filename} at {THERMAL_FPS} FPS")
                    else:
                        print("Error: Cannot start recording. Waiting for streams to provide frames...")
                        is_recording = False  # Failed to start

                else:
                    # --- Stop Recording ---
                    print("--- STOPPING RECORDING ---")
                    if rgb_writer:
                        rgb_writer.release()
                        rgb_writer = None
                        print("RGB recording saved.")
                    if thermal_writer:
                        thermal_writer.release()
                        thermal_writer = None
                        print("Thermal recording saved.")

            # --- Write Frames if Recording ---
            if is_recording and rgb_writer and last_rgb_frame is not None:
                rgb_writer.write(last_rgb_frame)

            if is_recording and thermal_writer and last_thermal_frame is not None:
                thermal_writer.write(last_thermal_frame)

    finally:
        # --- Cleanup ---
        print("Cleaning up...")

        # Stop the capture threads
        rgb_thread.stop()
        thermal_thread.stop()

        # Wait for threads to finish
        rgb_thread.join()
        thermal_thread.join()

        # Release any writers that are still open
        if rgb_writer:
            rgb_writer.release()
            print("RGB writer closed.")
        if thermal_writer:
            thermal_writer.release()
            print("Thermal writer closed.")

        cv2.destroyAllWindows()
        print("All windows closed. Exiting.")