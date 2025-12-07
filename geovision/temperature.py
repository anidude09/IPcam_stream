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
        except requests.RequestException as exc:
            print(f"TemperatureClient.get_roi_stats error: {exc}")
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
        # Validate coordinates
        if x < 0 or y < 0:
            print(f"[TemperatureClient] Invalid coordinates: ({x}, {y}) - must be non-negative")
            return None
            
        url = self._url("GetDotTemperature")
        # Match exact XML structure from documentation
        payload = f"""<?xml version="1.0" encoding="UTF-8"?>
<config version="1.0" xmlns="http://www.ipc.com/ver10">
    <dotTemperature>
        <hotX>{x}</hotX>
        <hotY>{y}</hotY>
    </dotTemperature>
</config>"""
        headers = {"Content-Type": "application/xml"}
        try:
            print(f"[TemperatureClient] Requesting temperature at ({x}, {y})")
            response = requests.post(
                url,
                data=payload,
                headers=headers,
                auth=self._auth(),
                timeout=self.timeout,
            )
            response.raise_for_status()
            print(f"[TemperatureClient] Response received (status: {response.status_code})")
            return _parse_dot_response(response.text, self.temp_conversion_factor, self.temp_offset)
        except requests.Timeout:
            print(f"[TemperatureClient] Request timed out after {self.timeout}s")
            return None
        except requests.ConnectionError as exc:
            print(f"[TemperatureClient] Connection error: {exc}")
            return None
        except requests.RequestException as exc:
            print(f"[TemperatureClient] Request error: {exc}")
            if hasattr(exc, 'response') and exc.response is not None:
                print(f"[TemperatureClient] Error response: {exc.response.text[:500]}")  # Limit response length
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
    except ET.ParseError as exc:
        print(f"ROI XML parse error: {exc}\nResponse: {xml_text}")
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
    Response structure should be in <config> with <dotTemperature> containing:
    - <temperature> (value in hundredths, e.g., 2835 = 28.35°C)
    - <hotX> (confirmed X coordinate)
    - <hotY> (confirmed Y coordinate)
    """
    if not xml_text or not xml_text.strip():
        print("[Parse Error] Empty XML response")
        return None
        
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError as exc:
        print(f"[Parse Error] XML parse error: {exc}")
        return None

    # Try to find nodes - they might be directly under root or in dotTemperature
    dot_temp_elem = root.find(".//{*}dotTemperature")
    if dot_temp_elem is not None:
        temperature_node = dot_temp_elem.find(".//{*}temperature")
        x_node = dot_temp_elem.find(".//{*}hotX")
        y_node = dot_temp_elem.find(".//{*}hotY")
    else:
        # Fallback: search in entire document
        temperature_node = root.find(".//{*}temperature")
        x_node = root.find(".//{*}hotX")
        y_node = root.find(".//{*}hotY")
    
    # Check for missing nodes
    missing = []
    if temperature_node is None:
        missing.append("temperature")
    if x_node is None:
        missing.append("hotX")
    if y_node is None:
        missing.append("hotY")
    
    if missing:
        print(f"[Parse Error] Missing nodes: {', '.join(missing)}")
        # List available nodes for debugging
        available = [elem.tag.split('}')[-1] if '}' in elem.tag else elem.tag for elem in root.iter()]
        print(f"[Parse Error] Available nodes: {available[:20]}")  # Limit to first 20
        return None

    try:
        temp_raw = temperature_node.text
        x_raw = x_node.text
        y_raw = y_node.text
        
        if temp_raw is None or x_raw is None or y_raw is None:
            print(f"[Parse Error] Node text is None: temp={temp_raw}, x={x_raw}, y={y_raw}")
            return None
        
        temp_raw_int = int(temp_raw)
        
        # Use configured conversion factor (default: divide by 100 for hundredths)
        temp = (float(temp_raw_int) / conversion_factor) + temp_offset
        x_val = int(x_raw)
        y_val = int(y_raw)
        
        print(f"[Parse] Temperature: {temp:.2f}°C (raw={temp_raw_int}) at ({x_val}, {y_val})")
        
        return temp, x_val, y_val
    except (TypeError, ValueError) as e:
        print(f"[Parse Error] Value conversion error: {e}")
        return None


__all__ = [
    "TemperatureClient",
    "get_roi_stats",
    "get_dot_temperature",
]
