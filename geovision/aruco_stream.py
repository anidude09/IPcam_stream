"""Threaded RTSP stream with ArUco marker detection overlay."""
from __future__ import annotations

import time
import threading
from typing import Any, Dict, List, Optional, Tuple

import cv2
import numpy as np

from .config import CameraCredentials, StreamProfile, configure_opencv_transport
from .streams import RTSPStream


# Colours used in the annotation overlay
_BOX_COLOUR: Tuple[int, int, int] = (0, 230, 120)   # vibrant green
_ID_BG_COLOUR: Tuple[int, int, int] = (0, 140, 70)
_ID_TEXT_COLOUR: Tuple[int, int, int] = (255, 255, 255)
_CORNER_COLOUR: Tuple[int, int, int] = (0, 200, 255)  # cyan dots on corners


class ArucoStream(RTSPStream):
    """RGB RTSP stream that periodically detects ArUco markers and annotates frames.

    Detection is intentionally throttled (``detect_every_n`` frames) so it
    stays cheap even at 30 fps.  The last known set of detections is drawn
    on *every* frame so the overlay never flickers between detection runs.
    """

    def __init__(
        self,
        credentials: CameraCredentials,
        profile: StreamProfile,
        name: str = "ArUco",
        detect_every_n: int = 10,
        aruco_dict_id: int = cv2.aruco.DICT_4X4_50,
        reconnect_delay: float = 2.0,
        buffer_size: int = 1,
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
        # Slightly relax thresholds for real-world outdoor / print quality
        params.adaptiveThreshWinSizeMin = 3
        params.adaptiveThreshWinSizeMax = 53
        params.adaptiveThreshWinSizeStep = 4
        params.minMarkerPerimeterRate = 0.02
        self._detector = cv2.aruco.ArucoDetector(dictionary, params)

        self._frame_counter: int = 0
        self._last_corners: List[np.ndarray] = []
        self._last_ids: Optional[np.ndarray] = None
        self._detection_lock = threading.Lock()
        self._last_detection_ts: float = 0.0

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

            # Run ArUco detection every N frames
            if self._frame_counter % self.detect_every_n == 0:
                self._run_detection(frame)

            # Annotate *every* frame with last known detections
            annotated = self._annotate(frame)

            with self._lock:
                self._latest_frame = annotated

    # ------------------------------------------------------------------
    # Detection + annotation helpers
    # ------------------------------------------------------------------

    def _run_detection(self, frame: np.ndarray) -> None:
        """Detect ArUco markers in *frame* and cache results."""
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        corners, ids, _ = self._detector.detectMarkers(gray)
        with self._detection_lock:
            self._last_corners = list(corners) if corners else []
            self._last_ids = ids if ids is not None else None
            self._last_detection_ts = time.time()

    def _annotate(self, frame: np.ndarray) -> np.ndarray:
        """Draw detections from last run onto a copy of *frame*."""
        out = frame.copy()

        with self._detection_lock:
            corners = list(self._last_corners)
            ids = self._last_ids.copy() if self._last_ids is not None else None

        if not corners or ids is None:
            # No detections — draw a small "scanning" indicator
            _draw_scanning_indicator(out)
            return out

        # Draw the standard ArUco overlay (green border poly)
        cv2.aruco.drawDetectedMarkers(out, corners, ids, _BOX_COLOUR)

        # Add per-tag ID label and corner dots
        for corner_set, marker_id in zip(corners, ids.flatten()):
            pts = corner_set.reshape(4, 2).astype(int)

            # Coloured corner dots
            for pt in pts:
                cv2.circle(out, tuple(pt), 5, _CORNER_COLOUR, -1, lineType=cv2.LINE_AA)

            # ID label above the top-left corner
            label_pt = (int(pts[0][0]), max(0, int(pts[0][1]) - 10))
            _draw_id_label(out, f"ID: {marker_id}", label_pt)

        return out


# ------------------------------------------------------------------
# Module-level drawing utilities
# ------------------------------------------------------------------

def _draw_id_label(img: np.ndarray, text: str, origin: Tuple[int, int]) -> None:
    """Render a filled-background ID label at *origin* (top-left of text box)."""
    font = cv2.FONT_HERSHEY_SIMPLEX
    scale = 0.65
    thickness = 2
    (tw, th), baseline = cv2.getTextSize(text, font, scale, thickness)
    pad = 4
    x, y = origin
    # Clamp to image bounds
    y = max(th + pad * 2, y)
    x1, y1 = x, y - th - pad * 2
    x2, y2 = x + tw + pad * 2, y
    cv2.rectangle(img, (x1, y1), (x2, y2), _ID_BG_COLOUR, -1)
    cv2.putText(img, text, (x1 + pad, y2 - pad), font, scale, _ID_TEXT_COLOUR, thickness, cv2.LINE_AA)


def _draw_scanning_indicator(img: np.ndarray) -> None:
    """Draw a subtle 'Scanning…' text in the bottom-left corner."""
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
