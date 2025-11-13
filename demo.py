"""Simple RGB stream viewer built on the GeoVision modular package."""
from __future__ import annotations

import time

import cv2

from geovision.config import DEFAULT_CREDENTIALS, RGB_STREAM
from geovision.streams import RTSPStream


WINDOW_NAME = "GeoVision RGB Stream (press 'q' to quit)"


def main() -> None:
    stream = RTSPStream(credentials=DEFAULT_CREDENTIALS, profile=RGB_STREAM, name="RGB")
    stream.start()
    print(f"Attempting to connect to {stream.rtsp_url}")

    try:
        while True:
            frame = stream.latest_frame()
            if frame is None:
                time.sleep(0.05)
                continue
            cv2.imshow(WINDOW_NAME, frame)
            if cv2.waitKey(1) & 0xFF == ord('q'):
                break
    finally:
        stream.stop()
        cv2.destroyAllWindows()
        print("Stream closed.")


if __name__ == "__main__":
    main()
