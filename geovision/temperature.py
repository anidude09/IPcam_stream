"""Camera temperature API helpers."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional, Tuple
import xml.etree.ElementTree as ET

import requests
from requests.auth import HTTPBasicAuth

from .config import CameraCredentials, StreamProfile, DEFAULT_CREDENTIALS, THERMAL_STREAM


@dataclass(frozen=True)
class TemperatureClient:
    credentials: CameraCredentials = DEFAULT_CREDENTIALS
    channel: int = THERMAL_STREAM.channel
    timeout: float = 3.0
    # Temperature conversion factor: divide raw value by this to get Celsius
    # Default is 100 (hundredths) per API documentation
    # Some cameras might use 10 (tenths) or 1 (direct Celsius)
    temp_conversion_factor: float = 100.0
    # Optional temperature offset to apply (for calibration)
    temp_offset: float = 0.0

    def _auth(self) -> HTTPBasicAuth:
        return HTTPBasicAuth(self.credentials.username, self.credentials.password)

    def _url(self, suffix: str) -> str:
        return self.credentials.http_url(f"{suffix}/{self.channel}")

    def get_roi_stats(self) -> Optional[Dict[str, float]]:
        url = self._url("GetTemperatureCurrentInfo")
        try:
            response = requests.get(url, auth=self._auth(), timeout=self.timeout)
            response.raise_for_status()
            return _parse_roi_response(response.text)
        except requests.RequestException:
            return None

    def get_dot_temperature(self, x: int, y: int) -> Optional[Tuple[float, int, int]]:
        """
        Get temperature at specific pixel coordinates.
        According to API docs: POST http://<host>[:port]/GetDotTemperature[/channelId]
        
        Args:
            x: X coordinate (0-10000 normalized)
            y: Y coordinate (0-10000 normalized)
            
        Returns:
            Tuple of (temperature_celsius, x_coord, y_coord) or None on error
        """
        if x < 0 or y < 0:
            return None
            
        url = self._url("GetDotTemperature")
        payload = f"""<?xml version="1.0" encoding="UTF-8"?>
<config version="1.0" xmlns="http://www.ipc.com/ver10">
    <dotTemperature>
        <hotX>{x}</hotX>
        <hotY>{y}</hotY>
    </dotTemperature>
</config>"""
        headers = {"Content-Type": "application/xml"}
        try:
            response = requests.post(
                url,
                data=payload,
                headers=headers,
                auth=self._auth(),
                timeout=self.timeout,
            )
            response.raise_for_status()
            return _parse_dot_response(response.text, self.temp_conversion_factor, self.temp_offset)
        except requests.Timeout:
            print(f"[Error] Temperature request timed out")
            return None
        except requests.ConnectionError:
            print(f"[Error] Cannot connect to camera for temperature")
            return None
        except requests.RequestException as exc:
            print(f"[Error] Temperature request failed: {exc}")
            return None


def get_roi_stats(credentials: CameraCredentials = DEFAULT_CREDENTIALS, stream: StreamProfile = THERMAL_STREAM) -> Optional[Dict[str, float]]:
    return TemperatureClient(credentials=credentials, channel=stream.channel).get_roi_stats()


def get_dot_temperature(
    x: int,
    y: int,
    credentials: CameraCredentials = DEFAULT_CREDENTIALS,
    stream: StreamProfile = THERMAL_STREAM,
) -> Optional[Tuple[float, int, int]]:
    return TemperatureClient(credentials=credentials, channel=stream.channel).get_dot_temperature(x, y)


def _parse_roi_response(xml_text: str) -> Optional[Dict[str, float]]:
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError:
        return None

    def _read(tag: str) -> Optional[float]:
        node = root.find(f".//{{*}}{tag}Temper/{{*}}value")
        if node is None or node.text is None:
            return None
        try:
            return float(node.text) / 100.0
        except ValueError:
            return None

    data = {k: v for k, v in {"max": _read("max"), "min": _read("min"), "avg": _read("avg")}.items() if v is not None}
    return data or None


def _parse_dot_response(xml_text: str, conversion_factor: float = 100.0, temp_offset: float = 0.0) -> Optional[Tuple[float, int, int]]:
    """
    Parse the GetDotTemperature API response.
    """
    if not xml_text or not xml_text.strip():
        return None
        
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError:
        return None

    # Try to find nodes - they might be directly under root or in dotTemperature
    dot_temp_elem = root.find(".//{*}dotTemperature")
    if dot_temp_elem is not None:
        temperature_node = dot_temp_elem.find(".//{*}temperature")
        x_node = dot_temp_elem.find(".//{*}hotX")
        y_node = dot_temp_elem.find(".//{*}hotY")
    else:
        temperature_node = root.find(".//{*}temperature")
        x_node = root.find(".//{*}hotX")
        y_node = root.find(".//{*}hotY")
    
    if temperature_node is None or x_node is None or y_node is None:
        return None

    try:
        temp_raw = temperature_node.text
        x_raw = x_node.text
        y_raw = y_node.text
        
        if temp_raw is None or x_raw is None or y_raw is None:
            return None
        
        temp = (float(int(temp_raw)) / conversion_factor) + temp_offset
        return temp, int(x_raw), int(y_raw)
    except (TypeError, ValueError):
        return None


__all__ = [
    "TemperatureClient",
    "get_roi_stats",
    "get_dot_temperature",
]
