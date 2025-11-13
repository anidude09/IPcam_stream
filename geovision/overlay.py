"""Drawing helpers for OpenCV frames."""
from __future__ import annotations

from typing import Tuple

import cv2
import numpy as np


Color = Tuple[int, int, int]


def draw_crosshair(frame: np.ndarray, center: Tuple[int, int], color: Color = (0, 255, 0), radius: int = 7) -> None:
    x, y = center
    cv2.circle(frame, (x, y), radius, color, 2)
    cv2.line(frame, (x - 15, y), (x + 15, y), color, 1)
    cv2.line(frame, (x, y - 15), (x, y + 15), color, 1)


def draw_label(frame: np.ndarray, text: str, anchor: Tuple[int, int], color: Color = (0, 255, 255)) -> None:
    x, y = anchor
    font = cv2.FONT_HERSHEY_SIMPLEX
    (text_w, text_h), _ = cv2.getTextSize(text, font, 0.7, 2)
    overlay = frame.copy()
    box_coords = ((x + 10, y - 10 - text_h), (x + 20 + text_w, y))
    cv2.rectangle(overlay, box_coords[0], box_coords[1], (0, 0, 0), -1)
    frame[:] = cv2.addWeighted(overlay, 0.6, frame, 0.4, 0)
    cv2.putText(frame, text, (x + 15, y - 10), font, 0.7, color, 2)


__all__ = ["draw_crosshair", "draw_label"]
