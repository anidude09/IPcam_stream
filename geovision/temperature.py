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
        url = self._url("GetDotTemperature")
        payload = f"""<?xml version=\"1.0\" encoding=\"UTF-8\"?>
<config version=\"1.0\" xmlns=\"http://www.ipc.com/ver10\">
    <dotTemperature>
        <hotX>{x}</hotX>
        <hotY>{y}</hotY>
    </dotTemperature>
</config>"""
        headers = {"Content-Type": "application/xml"}
        try:
            print(f"[TemperatureClient] Requesting temperature at ({x}, {y}) from {url}")
            response = requests.post(
                url,
                data=payload,
                headers=headers,
                auth=self._auth(),
                timeout=self.timeout,
            )
            response.raise_for_status()
            print(f"[TemperatureClient] Response status: {response.status_code}")
            print(f"[TemperatureClient] Response body: {response.text[:500]}")  # First 500 chars
            return _parse_dot_response(response.text)
        except requests.RequestException as exc:
            print(f"[TemperatureClient] Request error: {exc}")
            if hasattr(exc, 'response') and exc.response is not None:
                print(f"[TemperatureClient] Error response: {exc.response.text[:500]}")
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


def _parse_dot_response(xml_text: str) -> Optional[Tuple[float, int, int]]:
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError as exc:
        print(f"[Parse Error] Dot XML parse error: {exc}\nResponse: {xml_text[:500]}")
        return None

    temperature_node = root.find(".//{*}temperature")
    x_node = root.find(".//{*}hotX")
    y_node = root.find(".//{*}hotY")
    
    if temperature_node is None:
        print(f"[Parse Error] Could not find temperature node in XML")
    if x_node is None:
        print(f"[Parse Error] Could not find hotX node in XML")
    if y_node is None:
        print(f"[Parse Error] Could not find hotY node in XML")
    
    if not all([temperature_node is not None, x_node is not None, y_node is not None]):
        print(f"[Parse Error] Missing required nodes. XML: {xml_text[:500]}")
        return None

    try:
        temp_raw = temperature_node.text
        x_raw = x_node.text
        y_raw = y_node.text
        
        temp = float(temp_raw) / 100.0
        x_val = int(x_raw)
        y_val = int(y_raw)
        
        print(f"[Parse Success] Parsed: temp_raw={temp_raw}, x_raw={x_raw}, y_raw={y_raw}")
        print(f"[Parse Success] Converted: temp={temp:.2f}°C, x={x_val}, y={y_val}")
        
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
