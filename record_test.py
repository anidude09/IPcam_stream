"""Dual-stream viewer and recorder leveraging the modular GeoVision package."""
from __future__ import annotations

import time
from datetime import datetime

import cv2

from geovision.config import DEFAULT_CREDENTIALS, RGB_STREAM, THERMAL_STREAM
from geovision.streams import RTSPStream

FOURCC_CODEC = "XVID"


class VideoRecorder:
    def __init__(self, filename: str, fps: float, frame_size: tuple[int, int]) -> None:
        self.writer = cv2.VideoWriter(
            filename,
            cv2.VideoWriter_fourcc(*FOURCC_CODEC),
            fps,
            frame_size,
        )

    def write(self, frame):
        self.writer.write(frame)

    def close(self):
        if self.writer:
            self.writer.release()
            self.writer = None


WINDOW_RGB = "RGB Stream (Press 'r' to record, 'q' to quit)"
WINDOW_THERMAL = "Thermal Stream (Press 'r' to record, 'q' to quit)"


def main() -> None:
    rgb_stream = RTSPStream(DEFAULT_CREDENTIALS, RGB_STREAM, "RGB")
    thermal_stream = RTSPStream(DEFAULT_CREDENTIALS, THERMAL_STREAM, "Thermal")
    rgb_stream.start()
    thermal_stream.start()

    is_recording = False
    rgb_recorder: VideoRecorder | None = None
    thermal_recorder: VideoRecorder | None = None

    try:
        while True:
            rgb_frame = rgb_stream.latest_frame()
            thermal_frame = thermal_stream.latest_frame()

            if rgb_frame is not None:
                display_rgb = rgb_frame.copy()
                if is_recording:
                    cv2.circle(display_rgb, (30, 30), 15, (0, 0, 255), -1)
                cv2.imshow(WINDOW_RGB, display_rgb)

            if thermal_frame is not None:
                display_thermal = thermal_frame.copy()
                if is_recording:
                    cv2.circle(display_thermal, (30, 30), 15, (0, 0, 255), -1)
                cv2.imshow(WINDOW_THERMAL, display_thermal)

            key = cv2.waitKey(1) & 0xFF
            if key == ord('q'):
                print("'q' pressed. Quitting...")
                break

            if key == ord('r'):
                is_recording = not is_recording
                if is_recording:
                    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                    if rgb_frame is not None:
                        h, w, _ = rgb_frame.shape
                        rgb_recorder = VideoRecorder(
                            f"rgb_{timestamp}.avi",
                            RGB_STREAM.expected_fps or 30.0,
                            (w, h),
                        )
                    if thermal_frame is not None:
                        h_t, w_t, _ = thermal_frame.shape
                        thermal_recorder = VideoRecorder(
                            f"thermal_{timestamp}.avi",
                            THERMAL_STREAM.expected_fps or 15.0,
                            (w_t, h_t),
                        )
                    print("--- STARTING RECORDING ---")
                else:
                    print("--- STOPPING RECORDING ---")
                    if rgb_recorder:
                        rgb_recorder.close()
                        rgb_recorder = None
                        print("RGB recording saved.")
                    if thermal_recorder:
                        thermal_recorder.close()
                        thermal_recorder = None
                        print("Thermal recording saved.")

            if is_recording:
                if rgb_recorder and rgb_frame is not None:
                    rgb_recorder.write(rgb_frame)
                if thermal_recorder and thermal_frame is not None:
                    thermal_recorder.write(thermal_frame)

            time.sleep(0.01)
    finally:
        print("Cleaning up...")
        if rgb_recorder:
            rgb_recorder.close()
        if thermal_recorder:
            thermal_recorder.close()
        rgb_stream.stop()
        thermal_stream.stop()
        cv2.destroyAllWindows()
        print("All windows closed. Exiting.")


if __name__ == "__main__":
    main()
