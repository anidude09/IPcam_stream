"""Configuration utilities for GeoVision cameras."""
from __future__ import annotations

from dataclasses import dataclass
import os
from typing import Optional


@dataclass(frozen=True)
class CameraCredentials:
    """Authentication details required to talk to the GeoVision camera."""

    ip_address: str
    username: str
    password: str

    def rtsp_url(self, profile: str, port: int = 554, transport: str = "rtsp") -> str:
        """Return a full RTSP URL for the given stream profile."""
        return f"{transport}://{self.username}:{self.password}@{self.ip_address}:{port}/{profile}"

    def http_url(self, path: str, scheme: str = "http") -> str:
        """Return a full HTTP URL for the given API path."""
        normalized_path = path.lstrip("/")
        return f"{scheme}://{self.ip_address}/{normalized_path}"


@dataclass(frozen=True)
class StreamProfile:
    """Describes the properties of a camera stream profile."""

    profile_id: str
    channel: int
    expected_fps: Optional[float] = None
    # Native sensor resolution (for thermal: actual IR sensor pixels, not video resolution)
    sensor_width: Optional[int] = None
    sensor_height: Optional[int] = None


DEFAULT_CREDENTIALS = CameraCredentials(
    ip_address=os.getenv("GEOVISION_IP", "192.168.0.10"),
    username=os.getenv("GEOVISION_USER", "admin"),
    password=os.getenv("GEOVISION_PASS", "admin123"),
)

RGB_STREAM = StreamProfile(profile_id=os.getenv("GEOVISION_RGB_PROFILE", "profile1"), channel=1, expected_fps=30.0)

# GeoVision API uses NORMALIZED coordinates, not pixel coordinates!
# Based on API response examples showing values like xpos=3671, ypos=7864
# The coordinate space appears to be 0-10000 (normalized)
THERMAL_API_COORD_MAX = int(os.getenv("THERMAL_API_COORD_MAX", "10000"))

THERMAL_STREAM = StreamProfile(
    profile_id=os.getenv("GEOVISION_THERMAL_PROFILE", "profile4"),
    channel=2,
    expected_fps=15.0,
    sensor_width=THERMAL_API_COORD_MAX,  # API uses normalized coords 0-10000
    sensor_height=THERMAL_API_COORD_MAX   # API uses normalized coords 0-10000
)


def configure_opencv_transport(transport: str = "tcp") -> None:
    """Ensure OpenCV uses the provided RTSP transport mode via an env variable."""
    os.environ["OPENCV_FFMPEG_CAPTURE_OPTIONS"] = f"rtsp_transport;{transport}"


__all__ = [
    "CameraCredentials",
    "StreamProfile",
    "DEFAULT_CREDENTIALS",
    "RGB_STREAM",
    "THERMAL_STREAM",
    "configure_opencv_transport",
]
