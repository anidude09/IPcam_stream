"""Processing helpers for RGM thermal frames."""
from __future__ import annotations

import cv2
import numpy as np


def raw_to_celsius(raw_map: np.ndarray) -> np.ndarray:
    """Convert raw sensor units (hundredths of Kelvin) to Celsius."""
    return (raw_map.astype(np.float32) / 100.0) - 273.15


def c_to_f_scalar(c: float) -> float:
    """Convert Celsius to Fahrenheit."""
    return c * 9.0 / 5.0 + 32.0


def colorize_celsius(temp_c: np.ndarray, c_min: float, c_max: float) -> np.ndarray:
    """Apply an Inferno colormap to a Celsius temperature map."""
    scale = 255.0 / max(c_max - c_min, 1e-6)
    disp8 = np.clip((temp_c - c_min) * scale, 0, 255).astype(np.uint8)
    return cv2.applyColorMap(disp8, cv2.COLORMAP_INFERNO)


def overlay_box(img: np.ndarray, text: str, x: int = 10, y: int = 10) -> np.ndarray:
    """Draw a semi-transparent label box with text onto the image."""
    height = img.shape[0]
    target_px = max(14, int(height * 0.025))
    font = cv2.FONT_HERSHEY_SIMPLEX
    font_scale = target_px / 30.0
    thickness = max(1, int(target_px / 12))
    (text_w, text_h), _ = cv2.getTextSize(text, font, font_scale, thickness)
    pad = max(6, int(target_px * 0.25))
    x1, y1 = x, y
    x2, y2 = x1 + text_w + 2 * pad, y1 + text_h + 2 * pad
    cv2.rectangle(img, (x1, y1), (x2, y2), (16, 16, 16), -1)
    cv2.rectangle(img, (x1, y1), (x2, y2), (180, 180, 180), 1)
    cv2.putText(
        img,
        text,
        (x1 + pad, y1 + text_h + pad),
        font,
        font_scale,
        (255, 255, 255),
        thickness,
        cv2.LINE_AA,
    )
    return img

