"""Threaded RTSP stream helpers built on top of OpenCV."""
from __future__ import annotations

import threading
import time
from typing import Dict, Generator, Optional, Tuple

import cv2
import numpy as np

from .config import CameraCredentials, StreamProfile, configure_opencv_transport


class RTSPStream:
    """Manage a single RTSP stream in a background thread."""

    def __init__(
        self,
        credentials: CameraCredentials,
        profile: StreamProfile,
        name: str,
        reconnect_delay: float = 2.0,
        buffer_size: int = 1,
    ) -> None:
        self.credentials = credentials
        self.profile = profile
        self.name = name
        self.reconnect_delay = reconnect_delay
        self.buffer_size = buffer_size

        self._capture: Optional[cv2.VideoCapture] = None
        self._lock = threading.Lock()
        self._latest_frame: Optional[np.ndarray] = None
        self._frame_id: int = 0
        self._running = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._jpeg_cache_lock = threading.Lock()
        self._jpeg_cache: Dict[int, Tuple[int, bytes]] = {}

    @property
    def rtsp_url(self) -> str:
        return self.credentials.rtsp_url(self.profile.profile_id)

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return

        configure_opencv_transport("tcp")
        self._running.set()
        self._thread = threading.Thread(target=self._capture_loop, name=f"RTSPStream-{self.name}", daemon=True)
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

    def _set_latest_frame(self, frame: np.ndarray) -> None:
        with self._lock:
            self._latest_frame = frame
            self._frame_id += 1

    def frame_generator(self, wait_timeout: float = 0.1) -> Generator[np.ndarray, None, None]:
        """Yield frames as they arrive. Blocks until frames become available."""
        while self._running.is_set():
            frame = self.latest_frame(copy=True)
            if frame is not None:
                yield frame
            else:
                time.sleep(wait_timeout)

    def mjpeg_generator(
        self,
        framerate_hint: Optional[float] = None,
        jpeg_quality: int = 80,
        max_width: Optional[int] = None,
    ) -> Generator[bytes, None, None]:
        """Yield multipart JPEG bytes suitable for Flask streaming responses.

        Original defaults (for fallback): jpeg_quality=95 (OpenCV default),
        framerate_hint used as-is with full sleep.
        """
        delay = 1.0 / framerate_hint if framerate_hint and framerate_hint > 0 else 0.0
        encode_params = [cv2.IMWRITE_JPEG_QUALITY, jpeg_quality]
        last_sent_frame_id = -1
        while self._running.is_set():
            with self._lock:
                if self._latest_frame is None:
                    frame = None
                    frame_id = -1
                else:
                    # Skip encoding until a new captured frame arrives.
                    if self._frame_id == last_sent_frame_id:
                        frame = None
                    else:
                        frame = self._latest_frame.copy()
                    frame_id = self._frame_id
            if frame is None:
                time.sleep(0.002)
                continue

            encoded_bytes: Optional[bytes] = None
            with self._jpeg_cache_lock:
                cached = self._jpeg_cache.get(jpeg_quality)
                if cached and cached[0] == frame_id:
                    encoded_bytes = cached[1]
            if encoded_bytes is None:
                frame_to_encode = frame
                if max_width and max_width > 0 and frame.shape[1] > max_width:
                    scale = max_width / float(frame.shape[1])
                    new_h = max(1, int(frame.shape[0] * scale))
                    frame_to_encode = cv2.resize(frame, (max_width, new_h), interpolation=cv2.INTER_AREA)
                success, encoded = cv2.imencode(".jpg", frame_to_encode, encode_params)
                if not success:
                    continue
                encoded_bytes = encoded.tobytes()
                with self._jpeg_cache_lock:
                    self._jpeg_cache[jpeg_quality] = (frame_id, encoded_bytes)

            yield (
                b"--frame\r\n"
                b"Content-Type: image/jpeg\r\n\r\n" + encoded_bytes + b"\r\n"
            )
            last_sent_frame_id = frame_id

            if delay:
                time.sleep(delay)

    # --- Internal helpers ---

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

            self._set_latest_frame(frame)

    def _ensure_capture(self) -> Optional[cv2.VideoCapture]:
        if self._capture and self._capture.isOpened():
            return self._capture

        self._release_capture()
        cap = cv2.VideoCapture(self.rtsp_url, cv2.CAP_FFMPEG)
        cap.set(cv2.CAP_PROP_BUFFERSIZE, float(self.buffer_size))

        if not cap.isOpened():
            cap.release()
            return None

        self._capture = cap
        return self._capture

    def _release_capture(self) -> None:
        if self._capture:
            self._capture.release()
            self._capture = None


__all__ = ["RTSPStream"]
