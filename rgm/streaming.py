"""Threaded MJPEG streaming for the RGM thermal camera."""
from __future__ import annotations

import threading
import time
from typing import Dict, Iterable, Optional, Tuple

import cv2
import numpy as np

from .io import coerce_to_u16_2d, open_camera
from .processing import colorize_celsius, c_to_f_scalar, overlay_box, raw_to_celsius


CenterReading = Dict[str, Optional[float]]


class RGMThermalStream:
    """Capture frames from the local thermal camera and expose MJPEG + center temps."""

    def __init__(
        self,
        device_index: int = 0,
        use_msmf: bool = False,
        view_scale: int = 3,
        c_min_c: float = 20.0,
        c_max_c: float = 40.0,
        reconnect_delay: float = 1.0,
    ) -> None:
        self.device_index = device_index
        self.use_msmf = use_msmf
        self.view_scale = max(1, int(view_scale))
        self.c_min_c = c_min_c
        self.c_max_c = c_max_c
        self.reconnect_delay = reconnect_delay

        self._capture: Optional[cv2.VideoCapture] = None
        self._thread: Optional[threading.Thread] = None
        self._running = threading.Event()
        self._lock = threading.Lock()

        self._latest_frame: Optional[np.ndarray] = None
        self._last_center: CenterReading = {"raw": None, "temp_c": None, "temp_f": None}
        self._frame_counter = 0

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return

        self._ensure_capture()
        if self._capture is None:
            raise RuntimeError("Failed to initialize RGM camera capture")

        self._running.set()
        self._thread = threading.Thread(target=self._capture_loop, name="RGMStream", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._running.clear()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=2.0)
        self._thread = None
        self._release_capture()

    def latest_frame(self, copy: bool = True) -> Optional[np.ndarray]:
        with self._lock:
            if self._latest_frame is None:
                return None
            return self._latest_frame.copy() if copy else self._latest_frame

    def latest_center(self) -> CenterReading:
        with self._lock:
            return dict(self._last_center)

    def mjpeg_generator(self, framerate_hint: Optional[float] = None) -> Iterable[bytes]:
        delay = 1.0 / framerate_hint if framerate_hint and framerate_hint > 0 else 0.0
        while self._running.is_set():
            frame = self.latest_frame(copy=True)
            if frame is None:
                time.sleep(0.05)
                continue

            success, encoded = cv2.imencode(".jpg", frame)
            if not success:
                continue

            yield (
                b"--frame\r\n"
                b"Content-Type: image/jpeg\r\n\r\n" + encoded.tobytes() + b"\r\n"
            )

            if delay:
                time.sleep(delay)

    # Internal helpers -------------------------------------------------

    def _capture_loop(self) -> None:
        while self._running.is_set():
            cap = self._ensure_capture()
            if cap is None:
                time.sleep(self.reconnect_delay)
                continue

            ok, frame = cap.read()
            if not ok:
                self._release_capture()
                time.sleep(self.reconnect_delay)
                continue

            vis_frame, center = self._process_frame(cap, frame)
            with self._lock:
                self._latest_frame = vis_frame
                self._last_center = center

    def _process_frame(
        self, cap: cv2.VideoCapture, frame: np.ndarray
    ) -> Tuple[np.ndarray, CenterReading]:
        center: CenterReading = {"raw": None, "temp_c": None, "temp_f": None}
        gray16 = coerce_to_u16_2d(cap, frame)
        self._frame_counter = (self._frame_counter + 1) % 120

        if gray16 is None:
            vis_small = (
                frame
                if frame.ndim == 3
                else cv2.applyColorMap(frame.astype(np.uint8), cv2.COLORMAP_INFERNO)
            )
            height, width = vis_small.shape[:2]
            cx, cy = width // 2, height // 2
            if self._frame_counter == 1:
                print(
                    f"[RGM] Frame captured but not 16-bit (dtype={frame.dtype}, shape={frame.shape})",
                    flush=True,
                )
        else:
            temp_c_map = raw_to_celsius(gray16)
            height, width = temp_c_map.shape
            cy, cx = height // 2, width // 2
            center_c = float(temp_c_map[cy, cx])
            center_f = c_to_f_scalar(center_c)
            raw_center = int(gray16[cy, cx])
            center = {"raw": float(raw_center), "temp_c": center_c, "temp_f": center_f}
            vis_small = colorize_celsius(temp_c_map, self.c_min_c, self.c_max_c)
            if self._frame_counter == 1:
                print(
                    f"[RGM] 16-bit frame OK ({width}x{height}) raw_center={raw_center} temp={center_c:.2f}°C",
                    flush=True,
                )

        if self.view_scale != 1:
            vis = cv2.resize(
                vis_small, (width * self.view_scale, height * self.view_scale), interpolation=cv2.INTER_CUBIC
            )
            cx_out, cy_out = cx * self.view_scale, cy * self.view_scale
        else:
            vis = vis_small
            cx_out, cy_out = cx, cy

        radius = max(2, int(min(vis.shape[0], vis.shape[1]) * 0.012))
        cv2.circle(vis, (cx_out, cy_out), radius, (255, 255, 255), -1, lineType=cv2.LINE_AA)
        if center.get("temp_c") is not None:
            text = f"{center['temp_c']:.2f} °C  ({center['temp_f']:.2f} °F)"
            vis = overlay_box(vis, text, x=10, y=10)

        return vis, center

    def _ensure_capture(self) -> Optional[cv2.VideoCapture]:
        if self._capture and self._capture.isOpened():
            return self._capture
        self._release_capture()
        try:
            self._capture = open_camera(self.device_index, use_msmf=self.use_msmf)
        except RuntimeError as exc:
            print(f"[RGM] Camera open failed: {exc}")
            self._capture = None
        return self._capture

    def _release_capture(self) -> None:
        if self._capture:
            self._capture.release()
            self._capture = None

