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
            response = requests.post(
                url,
                data=payload,
                headers=headers,
                auth=self._auth(),
                timeout=self.timeout,
            )
            response.raise_for_status()
            return _parse_dot_response(response.text)
        except requests.RequestException as exc:
            print(f"TemperatureClient.get_dot_temperature error: {exc}")
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
        print(f"Dot XML parse error: {exc}\nResponse: {xml_text}")
        return None

    temperature_node = root.find(".//{*}temperature")
    x_node = root.find(".//{*}hotX")
    y_node = root.find(".//{*}hotY")
    if not all([temperature_node is not None, x_node is not None, y_node is not None]):
        return None

    try:
        temp = float(temperature_node.text) / 100.0
        x_val = int(x_node.text)
        y_val = int(y_node.text)
        return temp, x_val, y_val
    except (TypeError, ValueError):
        return None


__all__ = [
    "TemperatureClient",
    "get_roi_stats",
    "get_dot_temperature",
]
