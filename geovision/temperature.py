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
        """
        url = self._url("GetDotTemperature")
        # Match exact XML structure from documentation
        # version="" is optional per docs, but we'll include a version for compatibility
        payload = f"""<?xml version="1.0" encoding="UTF-8"?>
<config version="1.0" xmlns="http://www.ipc.com/ver10">
    <dotTemperature>
        <hotX>{x}</hotX>
        <hotY>{y}</hotY>
    </dotTemperature>
</config>"""
        headers = {"Content-Type": "application/xml"}
        try:
            print(f"[TemperatureClient] Requesting temperature at ({x}, {y}) from {url}")
            print(f"[TemperatureClient] Request payload:\n{payload}")
            response = requests.post(
                url,
                data=payload,
                headers=headers,
                auth=self._auth(),
                timeout=self.timeout,
            )
            response.raise_for_status()
            print(f"[TemperatureClient] Response status: {response.status_code}")
            print(f"[TemperatureClient] Response body:\n{response.text}")  # Full response for debugging
            return _parse_dot_response(response.text, self.temp_conversion_factor, self.temp_offset)
        except requests.RequestException as exc:
            print(f"[TemperatureClient] Request error: {exc}")
            if hasattr(exc, 'response') and exc.response is not None:
                print(f"[TemperatureClient] Error response: {exc.response.text}")
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
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError as exc:
        print(f"[Parse Error] Dot XML parse error: {exc}\nResponse: {xml_text}")
        return None

    # Try to find nodes - they might be directly under root or in dotTemperature
    # First try finding in dotTemperature element
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
    
    # Debug: print all nodes found
    print(f"[Parse Debug] Found nodes - temp: {temperature_node is not None}, hotX: {x_node is not None}, hotY: {y_node is not None}")
    if temperature_node is not None:
        print(f"[Parse Debug] temperature node text: {temperature_node.text}")
    if x_node is not None:
        print(f"[Parse Debug] hotX node text: {x_node.text}")
    if y_node is not None:
        print(f"[Parse Debug] hotY node text: {y_node.text}")
    
    if temperature_node is None:
        print(f"[Parse Error] Could not find temperature node in XML")
        print(f"[Parse Error] Available nodes: {[elem.tag for elem in root.iter()]}")
    if x_node is None:
        print(f"[Parse Error] Could not find hotX node in XML")
    if y_node is None:
        print(f"[Parse Error] Could not find hotY node in XML")
    
    if not all([temperature_node is not None, x_node is not None, y_node is not None]):
        print(f"[Parse Error] Missing required nodes. Full XML:\n{xml_text}")
        return None

    try:
        temp_raw = temperature_node.text
        x_raw = x_node.text
        y_raw = y_node.text
        
        temp_raw_int = int(temp_raw)
        
        # Temperature conversion using configured factor
        # Documentation suggests hundredths (e.g., 2835 = 28.35°C)
        # But let's also check if it might be in tenths or already in Celsius
        temp_hundredths = float(temp_raw_int) / 100.0
        temp_tenths = float(temp_raw_int) / 10.0
        temp_direct = float(temp_raw_int)
        
        print(f"[Parse Success] Raw values: temp_raw={temp_raw} (int={temp_raw_int}), x_raw={x_raw}, y_raw={y_raw}")
        print(f"[Parse Success] Conversion options:")
        print(f"  - Divided by 100: {temp_hundredths:.2f}°C")
        print(f"  - Divided by 10:  {temp_tenths:.2f}°C")
        print(f"  - Direct value:   {temp_direct:.2f}°C")
        
        # Use configured conversion factor
        temp = (float(temp_raw_int) / conversion_factor) + temp_offset
        x_val = int(x_raw)
        y_val = int(y_raw)
        
        print(f"[Parse Success] Using: temp={temp:.2f}°C (raw={temp_raw_int}, factor={conversion_factor}, offset={temp_offset}), x={x_val}, y={y_val}")
        
        return temp, x_val, y_val
    except (TypeError, ValueError) as e:
        print(f"[Parse Error] Value conversion error: {e}")
        print(f"[Parse Error] Values: temp={temperature_node.text if temperature_node is not None else 'None'}, x={x_node.text if x_node is not None else 'None'}, y={y_node.text if y_node is not None else 'None'}")
        return None


__all__ = [
    "TemperatureClient",
    "get_roi_stats",
    "get_dot_temperature",
]
