"""Interactive thermal viewer that uses the modular GeoVision package."""
from __future__ import annotations

import threading
import time
from typing import Dict

import cv2

from geovision.config import DEFAULT_CREDENTIALS, THERMAL_STREAM
from geovision.overlay import draw_crosshair, draw_label
from geovision.streams import RTSPStream
from geovision.temperature import TemperatureClient

WINDOW_NAME = "Thermal Stream - Click for Temp, 'q' to Quit"


class SharedState:
    def __init__(self) -> None:
        self.target_x = 192
        self.target_y = 144
        self.current_temp_c: float | None = None
        self.status_message = "Click to measure temperature..."
        self.running = True


state = SharedState()
client = TemperatureClient()


def mouse_callback(event, x, y, *_args):
    if event == cv2.EVENT_LBUTTONDOWN:
        print(f"New target set at: ({x}, {y})")
        state.target_x = x
        state.target_y = y
        state.current_temp_c = None
        state.status_message = "Fetching temp..."


def temperature_worker() -> None:
    last_position: Dict[str, int] = {"x": -1, "y": -1}
    while state.running:
        if (state.target_x, state.target_y) != (last_position["x"], last_position["y"]):
            result = client.get_dot_temperature(state.target_x, state.target_y)
            if result is None:
                state.status_message = "Failed to get temp"
            else:
                temp_c, x, y = result
                state.current_temp_c = temp_c
                state.target_x, state.target_y = x, y
                state.status_message = f"{temp_c:.2f} °C"
            last_position["x"] = state.target_x
            last_position["y"] = state.target_y
        time.sleep(0.5)
    print("Temperature worker exiting")


def main() -> None:
    stream = RTSPStream(credentials=DEFAULT_CREDENTIALS, profile=THERMAL_STREAM, name="Thermal")
    stream.start()

    cv2.namedWindow(WINDOW_NAME)
    cv2.setMouseCallback(WINDOW_NAME, mouse_callback)

    worker = threading.Thread(target=temperature_worker, daemon=True)
    worker.start()

    try:
        while True:
            frame = stream.latest_frame()
            if frame is None:
                time.sleep(0.05)
                continue

            display = frame.copy()
            draw_crosshair(display, (state.target_x, state.target_y))
            draw_label(display, state.status_message, (state.target_x, state.target_y))
            cv2.imshow(WINDOW_NAME, display)

            if cv2.waitKey(1) & 0xFF == ord('q'):
                break
    finally:
        print("Cleaning up...")
        state.running = False
        worker.join(timeout=2.0)
        stream.stop()
        cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
