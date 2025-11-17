"""Camera IO helpers for the RGM thermal sensor."""
from __future__ import annotations

from typing import Optional

import cv2
import numpy as np


def open_camera(index: int = 0, use_msmf: bool = False) -> cv2.VideoCapture:
    """Open a local camera using the preferred Windows backend."""
    backend = cv2.CAP_MSMF if use_msmf else cv2.CAP_DSHOW
    cap = cv2.VideoCapture(index, backend)
    if not cap.isOpened():
        fallback = cv2.CAP_DSHOW if use_msmf else cv2.CAP_MSMF
        cap = cv2.VideoCapture(index, fallback)
    if not cap.isOpened():
        raise RuntimeError(f"Could not open camera at index {index}")

    cap.set(cv2.CAP_PROP_CONVERT_RGB, 0)
    try:
        cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*"Y16 "))
    except Exception:
        pass
    return cap


def coerce_to_u16_2d(cap: cv2.VideoCapture, frame: np.ndarray) -> Optional[np.ndarray]:
    """Normalize various frame layouts to a 16-bit single-channel map."""
    if not isinstance(frame, np.ndarray):
        return None
    if frame.dtype == np.uint16 and frame.ndim == 2:
        return frame
    if frame.dtype == np.uint8 and frame.ndim == 2 and frame.shape[0] > 1:
        return frame.astype(np.uint16)
    if frame.ndim == 3 and frame.shape[2] in (3, 4):
        gray8 = (
            cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            if frame.shape[2] == 3
            else cv2.cvtColor(frame, cv2.COLOR_BGRA2GRAY)
        )
        return gray8.astype(np.uint16)
    if frame.dtype == np.uint8 and frame.ndim == 2 and frame.shape[0] == 1:
        w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)) or 640
        h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT)) or 480
        flat = frame.reshape(-1)
        if flat.size >= (w * h):
            y_plane = flat[: w * h].reshape(h, w)
            return y_plane.astype(np.uint16)
    return None

