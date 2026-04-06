"""Threaded RTSP stream with ArUco marker detection overlay and trail tracking.

Performance-tuned variant: half-res detection, narrower adaptive threshold
sweep, in-place annotation, and per-ID motion trails.

Fallback values (original before optimisation):
    detect_every_n          = 10
    adaptiveThreshWinSizeMax = 53
    adaptiveThreshWinSizeStep = 4
    detection resolution    = full (no downscale)
    _annotate               = frame.copy()  (separate allocation)
    trail tracking          = none
"""
from __future__ import annotations

import time
import threading
from collections import deque
from typing import Any, Dict, List, Optional, Tuple

import cv2
import numpy as np

from .config import CameraCredentials, StreamProfile, configure_opencv_transport
from .streams import RTSPStream


_BOX_COLOUR: Tuple[int, int, int] = (0, 230, 120)
_ID_BG_COLOUR: Tuple[int, int, int] = (0, 140, 70)
_ID_TEXT_COLOUR: Tuple[int, int, int] = (255, 255, 255)
_CORNER_COLOUR: Tuple[int, int, int] = (0, 200, 255)

_TRAIL_COLOURS: List[Tuple[int, int, int]] = [
    (255, 80, 80),
    (80, 255, 80),
    (80, 180, 255),
    (255, 255, 80),
    (255, 80, 255),
    (80, 255, 255),
    (255, 160, 50),
    (180, 80, 255),
]


def _trail_colour(marker_id: int) -> Tuple[int, int, int]:
    return _TRAIL_COLOURS[marker_id % len(_TRAIL_COLOURS)]


class ArucoStream(RTSPStream):
    """RGB RTSP stream with throttled ArUco detection, annotation, and motion trails."""

    def __init__(
        self,
        credentials: CameraCredentials,
        profile: StreamProfile,
        name: str = "ArUco",
        detect_every_n: int = 3,
        aruco_dict_id: int = cv2.aruco.DICT_4X4_50,
        reconnect_delay: float = 2.0,
        buffer_size: int = 1,
        trail_length: int = 120,
        trail_stale_s: float = 3.0,
    ) -> None:
        super().__init__(
            credentials=credentials,
            profile=profile,
            name=name,
            reconnect_delay=reconnect_delay,
            buffer_size=buffer_size,
        )
        self.detect_every_n = max(1, int(detect_every_n))

        dictionary = cv2.aruco.getPredefinedDictionary(aruco_dict_id)
        params = cv2.aruco.DetectorParameters()
        params.adaptiveThreshWinSizeMin = 3
        params.adaptiveThreshWinSizeMax = 23
        params.adaptiveThreshWinSizeStep = 8
        params.minMarkerPerimeterRate = 0.02
        self._detector = cv2.aruco.ArucoDetector(dictionary, params)

        self._frame_counter: int = 0
        self._last_corners: List[np.ndarray] = []
        self._last_ids: Optional[np.ndarray] = None
        self._detection_lock = threading.Lock()
        self._last_detection_ts: float = 0.0

        self._trail_maxlen = trail_length
        self._trail_stale_s = trail_stale_s
        self._trails: Dict[int, deque] = {}
        self._trail_last_seen: Dict[int, float] = {}

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def latest_detections(self) -> Dict[str, Any]:
        """Return the most recent detection results as a plain dict."""
        with self._detection_lock:
            ids = (
                self._last_ids.flatten().tolist()
                if self._last_ids is not None
                else []
            )
            return {
                "ids": ids,
                "count": len(ids),
                "timestamp": self._last_detection_ts,
            }

    # ------------------------------------------------------------------
    # Internal — override capture loop
    # ------------------------------------------------------------------

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

            self._frame_counter += 1

            if self._frame_counter % self.detect_every_n == 0:
                self._run_detection(frame)

            self._annotate_inplace(frame)

            self._set_latest_frame(frame)

    # ------------------------------------------------------------------
    # Detection + annotation helpers
    # ------------------------------------------------------------------

    def _run_detection(self, frame: np.ndarray) -> None:
        """Detect ArUco markers on a half-res copy and cache results."""
        h, w = frame.shape[:2]
        sw, sh = w * 3 // 4, h * 3 // 4
        small = cv2.resize(frame, (sw, sh), interpolation=cv2.INTER_LINEAR)
        gray = cv2.cvtColor(small, cv2.COLOR_BGR2GRAY)
        corners, ids, _ = self._detector.detectMarkers(gray)

        if corners:
            scale = w / sw
            corners = [c * scale for c in corners]

        now = time.time()
        with self._detection_lock:
            self._last_corners = list(corners) if corners else []
            self._last_ids = ids if ids is not None else None
            self._last_detection_ts = now

            if corners and ids is not None:
                for corner_set, marker_id in zip(corners, ids.flatten()):
                    mid = int(marker_id)
                    center = tuple(corner_set.reshape(4, 2).mean(axis=0).astype(int))
                    if mid not in self._trails:
                        self._trails[mid] = deque(maxlen=self._trail_maxlen)
                    self._trails[mid].append(center)
                    self._trail_last_seen[mid] = now

            stale = [
                mid for mid, ts in self._trail_last_seen.items()
                if now - ts > self._trail_stale_s
            ]
            for mid in stale:
                self._trails.pop(mid, None)
                self._trail_last_seen.pop(mid, None)

    def _annotate_inplace(self, frame: np.ndarray) -> None:
        """Draw detections and trails directly onto *frame* (no copy)."""
        with self._detection_lock:
            corners = list(self._last_corners)
            ids = self._last_ids.copy() if self._last_ids is not None else None
            trails_snapshot = {
                mid: list(trail) for mid, trail in self._trails.items()
            }

        for mid, pts in trails_snapshot.items():
            if len(pts) < 2:
                continue
            color = _trail_colour(mid)
            n = len(pts)
            for i in range(1, n):
                thickness = max(1, int(1 + 2 * i / n))
                cv2.line(frame, pts[i - 1], pts[i], color, thickness, cv2.LINE_AA)

        if not corners or ids is None:
            _draw_scanning_indicator(frame)
            return

        cv2.aruco.drawDetectedMarkers(frame, corners, ids, _BOX_COLOUR)

        for corner_set, marker_id in zip(corners, ids.flatten()):
            pts = corner_set.reshape(4, 2).astype(int)

            for pt in pts:
                cv2.circle(frame, tuple(pt), 5, _CORNER_COLOUR, -1, lineType=cv2.LINE_AA)

            label_pt = (int(pts[0][0]), max(0, int(pts[0][1]) - 10))
            _draw_id_label(frame, f"ID: {marker_id}", label_pt)


# ------------------------------------------------------------------
# Module-level drawing utilities
# ------------------------------------------------------------------

def _draw_id_label(img: np.ndarray, text: str, origin: Tuple[int, int]) -> None:
    font = cv2.FONT_HERSHEY_SIMPLEX
    scale = 0.65
    thickness = 2
    (tw, th), baseline = cv2.getTextSize(text, font, scale, thickness)
    pad = 4
    x, y = origin
    y = max(th + pad * 2, y)
    x1, y1 = x, y - th - pad * 2
    x2, y2 = x + tw + pad * 2, y
    cv2.rectangle(img, (x1, y1), (x2, y2), _ID_BG_COLOUR, -1)
    cv2.putText(img, text, (x1 + pad, y2 - pad), font, scale, _ID_TEXT_COLOUR, thickness, cv2.LINE_AA)


def _draw_scanning_indicator(img: np.ndarray) -> None:
    font = cv2.FONT_HERSHEY_SIMPLEX
    h, w = img.shape[:2]
    text = "Scanning for ArUco tags..."
    scale = 0.55
    thickness = 1
    (tw, th), _ = cv2.getTextSize(text, font, scale, thickness)
    pad = 8
    x, y = pad, h - pad
    cv2.rectangle(img, (x - pad, y - th - pad), (x + tw + pad, y + pad), (20, 20, 20), -1)
    cv2.putText(img, text, (x, y), font, scale, (160, 160, 160), thickness, cv2.LINE_AA)


__all__ = ["ArucoStream"]
