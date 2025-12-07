"""Core package for GeoVision camera streaming utilities."""

from .config import CameraCredentials, StreamProfile
from .streams import RTSPStream
from .temperature import get_roi_stats, get_dot_temperature
from .camera_manager import CameraManager, camera_manager

__all__ = [
    "CameraCredentials",
    "StreamProfile",
    "RTSPStream",
    "get_roi_stats",
    "get_dot_temperature",
    "CameraManager",
    "camera_manager",
]
