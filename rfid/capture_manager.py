"""
RFID Capture Manager - Captures frames from all camera streams when RFID tag is scanned.
Saves frames to disk and logs metadata to CSV.
"""
from __future__ import annotations

import csv
import os
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any, TYPE_CHECKING

import cv2
import numpy as np

if TYPE_CHECKING:
    from geovision.camera_manager import CameraManager
    from rgm.streaming import RGMThermalStream


# Default paths (relative to project root)
DEFAULT_DATA_DIR = "data"
DEFAULT_CAPTURES_DIR = "data/captures"
DEFAULT_CSV_FILE = "data/cattle_captures.csv"


class CaptureManager:
    """
    Manages RFID-triggered frame captures from multiple camera streams.
    Saves frames as JPEG files and logs metadata to CSV.
    """
    
    def __init__(
        self,
        data_dir: str = DEFAULT_DATA_DIR,
        captures_dir: str = DEFAULT_CAPTURES_DIR,
        csv_file: str = DEFAULT_CSV_FILE,
        camera_manager: Optional['CameraManager'] = None,
        rgm_stream: Optional['RGMThermalStream'] = None,
    ):
        self.data_dir = Path(data_dir)
        self.captures_dir = Path(captures_dir)
        self.csv_file = Path(csv_file)
        self.camera_manager = camera_manager
        self.rgm_stream = rgm_stream
        
        # Ensure directories exist
        self._setup_directories()
        
        # Initialize CSV if needed
        self._setup_csv()
    
    def _setup_directories(self) -> None:
        """Create data directories if they don't exist."""
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.captures_dir.mkdir(parents=True, exist_ok=True)
    
    def _setup_csv(self) -> None:
        """Initialize CSV file with headers if it doesn't exist."""
        if not self.csv_file.exists():
            with open(self.csv_file, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow([
                    'eid',
                    'timestamp',
                    'date',
                    'time',
                    'group',
                    'camera_id',
                    'rgb_frame_path',
                    'thermal_frame_path',
                    'rgm_frame_path',
                    'geovision_temp_c',
                    'rgm_temp_c',
                    'notes'
                ])
    
    def capture_on_rfid_scan(
        self,
        eid: str,
        group: str = "default",
        camera_id: Optional[str] = None,
        notes: str = ""
    ) -> Dict[str, Any]:
        """
        Capture frames from all streams when RFID tag is scanned.
        
        Args:
            eid: Electronic ID from RFID tag
            group: Group/session name for categorization
            camera_id: Specific GeoVision camera ID (None = first available)
            notes: Optional notes for this capture
            
        Returns:
            Dictionary with capture results and file paths
        """
        now = datetime.now()
        timestamp = now.isoformat(timespec='seconds')
        date_str = now.date().isoformat()
        time_str = now.time().strftime("%H:%M:%S")
        
        # Create safe filename from timestamp and EID
        safe_eid = self._sanitize_filename(eid)
        folder_name = f"{now.strftime('%Y-%m-%d_%H%M%S')}_{safe_eid}"
        capture_folder = self.captures_dir / folder_name
        capture_folder.mkdir(parents=True, exist_ok=True)
        
        print(f"[Capture] EID: {eid} | Group: {group} | Time: {time_str}")
        
        result = {
            'eid': eid,
            'timestamp': timestamp,
            'date': date_str,
            'time': time_str,
            'group': group,
            'camera_id': camera_id or 'none',
            'rgb_frame_path': '',
            'thermal_frame_path': '',
            'rgm_frame_path': '',
            'geovision_temp_c': '',
            'rgm_temp_c': '',
            'notes': notes,
            'success': False,
            'errors': []
        }
        
        # Capture GeoVision frames (includes temperature overlay)
        if self.camera_manager:
            gv_result = self._capture_geovision_frames(capture_folder, camera_id)
            result['rgb_frame_path'] = gv_result.get('rgb_frame_path', '')
            result['thermal_frame_path'] = gv_result.get('thermal_frame_path', '')
            result['camera_id'] = gv_result.get('camera_id', 'none')
            if gv_result.get('geovision_temp_c') is not None:
                result['geovision_temp_c'] = f"{gv_result['geovision_temp_c']:.2f}"
        else:
            result['errors'].append('No camera manager configured')
        
        # Capture RGM frame (includes temperature overlay)
        if self.rgm_stream:
            rgm_result = self._capture_rgm_frame(capture_folder)
            result['rgm_frame_path'] = rgm_result.get('rgm_frame_path', '')
            if rgm_result.get('rgm_temp_c') is not None:
                result['rgm_temp_c'] = f"{rgm_result['rgm_temp_c']:.2f}"
        else:
            result['errors'].append('No RGM stream configured')
        
        # Log to CSV
        self._log_to_csv(result)
        
        result['success'] = len(result['errors']) == 0 or (
            result['rgb_frame_path'] or 
            result['thermal_frame_path'] or 
            result['rgm_frame_path']
        )
        
        # Summary log
        temps = []
        if result['geovision_temp_c']:
            temps.append(f"GV:{result['geovision_temp_c']}°C")
        if result['rgm_temp_c']:
            temps.append(f"RGM:{result['rgm_temp_c']}°C")
        temp_str = ", ".join(temps) if temps else "no temps"
        print(f"[Capture] Complete: {temp_str} | Saved to: {folder_name}")
        
        return result
    
    def _draw_temperature_overlay(
        self,
        frame: np.ndarray,
        temp_c: Optional[float],
        label: str = "Center"
    ) -> np.ndarray:
        """Draw temperature overlay on frame."""
        if temp_c is None:
            return frame
        
        h, w = frame.shape[:2]
        
        # Draw crosshair at center
        cx, cy = w // 2, h // 2
        color = (0, 255, 255)  # Yellow
        cv2.line(frame, (cx - 15, cy), (cx + 15, cy), color, 2)
        cv2.line(frame, (cx, cy - 15), (cx, cy + 15), color, 2)
        cv2.circle(frame, (cx, cy), 8, color, 2)
        
        # Draw temperature text
        temp_text = f"{temp_c:.1f}C"
        font = cv2.FONT_HERSHEY_SIMPLEX
        font_scale = 0.8
        thickness = 2
        
        # Get text size for background
        (text_w, text_h), baseline = cv2.getTextSize(temp_text, font, font_scale, thickness)
        
        # Position: slightly above and to the right of center
        text_x = cx + 20
        text_y = cy - 10
        
        # Draw background rectangle
        padding = 5
        cv2.rectangle(
            frame,
            (text_x - padding, text_y - text_h - padding),
            (text_x + text_w + padding, text_y + padding),
            (0, 0, 0),
            -1
        )
        
        # Draw temperature text
        cv2.putText(frame, temp_text, (text_x, text_y), font, font_scale, color, thickness)
        
        # Draw label in top-left corner
        label_text = f"{label} Temp"
        cv2.putText(frame, label_text, (10, 25), font, 0.6, (255, 255, 255), 1)
        
        return frame
    
    def _capture_geovision_frames(
        self,
        capture_folder: Path,
        camera_id: Optional[str]
    ) -> Dict[str, str]:
        """Capture RGB and thermal frames from GeoVision camera."""
        result = {
            'rgb_frame_path': '',
            'thermal_frame_path': '',
            'camera_id': 'none',
            'geovision_temp_c': None
        }
        
        # Get camera - either specified or first available
        if camera_id:
            managed = self.camera_manager.get_camera(camera_id)
        else:
            cameras = self.camera_manager.get_all_cameras()
            managed = cameras[0] if cameras else None
        
        if not managed:
            return result
        
        result['camera_id'] = managed.config.id
        
        # Get center temperature first (for overlay)
        temp_c = None
        try:
            client = managed.get_temperature_client()
            temp_result = client.get_dot_temperature(5000, 5000)
            if temp_result:
                temp_c, _, _ = temp_result
                result['geovision_temp_c'] = temp_c
        except Exception:
            pass
        
        # Capture RGB frame
        if managed.rgb_stream:
            rgb_frame = managed.rgb_stream.latest_frame(copy=True)
            if rgb_frame is not None:
                rgb_path = capture_folder / "geovision_rgb.jpg"
                if cv2.imwrite(str(rgb_path), rgb_frame):
                    result['rgb_frame_path'] = str(rgb_path.as_posix())
        
        # Capture Thermal frame with temperature overlay
        if managed.thermal_stream:
            thermal_frame = managed.thermal_stream.latest_frame(copy=True)
            if thermal_frame is not None:
                # Add temperature overlay
                thermal_frame = self._draw_temperature_overlay(thermal_frame, temp_c, "GeoVision")
                thermal_path = capture_folder / "geovision_thermal.jpg"
                if cv2.imwrite(str(thermal_path), thermal_frame):
                    result['thermal_frame_path'] = str(thermal_path.as_posix())
        
        return result
    
    def _capture_rgm_frame(self, capture_folder: Path) -> Dict[str, str]:
        """Capture frame from RGM thermal camera (already has overlay)."""
        result = {'rgm_frame_path': '', 'rgm_temp_c': None}
        
        # Get RGM center temperature for CSV
        try:
            center_data = self.rgm_stream.latest_center()
            if center_data and 'temp_c' in center_data:
                result['rgm_temp_c'] = center_data['temp_c']
        except Exception:
            pass
        
        # RGM frame already has temperature overlay from streaming
        rgm_frame = self.rgm_stream.latest_frame(copy=True)
        if rgm_frame is not None:
            rgm_path = capture_folder / "rgm_thermal.jpg"
            if cv2.imwrite(str(rgm_path), rgm_frame):
                result['rgm_frame_path'] = str(rgm_path.as_posix())
        
        return result
    
    def _get_geovision_temperature(self, camera_id: str) -> Optional[float]:
        """Get center temperature from GeoVision thermal camera."""
        try:
            managed = self.camera_manager.get_camera(camera_id)
            if not managed:
                return None
            
            client = managed.get_temperature_client()
            result = client.get_dot_temperature(5000, 5000)
            
            if result:
                temp_c, _, _ = result
                return temp_c
        except Exception:
            pass
        return None
    
    def _get_rgm_temperature(self) -> Optional[float]:
        """Get center temperature from RGM thermal camera."""
        try:
            center_data = self.rgm_stream.latest_center()
            if center_data and 'temp_c' in center_data:
                return center_data['temp_c']
        except Exception:
            pass
        return None
    
    def _log_to_csv(self, result: Dict[str, Any]) -> None:
        """Append capture result to CSV file."""
        try:
            with open(self.csv_file, 'a', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow([
                    result['eid'],
                    result['timestamp'],
                    result['date'],
                    result['time'],
                    result['group'],
                    result['camera_id'],
                    result['rgb_frame_path'],
                    result['thermal_frame_path'],
                    result['rgm_frame_path'],
                    result['geovision_temp_c'],
                    result['rgm_temp_c'],
                    result['notes']
                ])
        except Exception as e:
            print(f"[Error] CSV write failed: {e}")
    
    @staticmethod
    def _sanitize_filename(text: str) -> str:
        """Remove invalid filename characters."""
        invalid_chars = '<>:"/\\|?*'
        for char in invalid_chars:
            text = text.replace(char, '_')
        return text.strip()


# Singleton instance (initialized by app.py)
capture_manager: Optional[CaptureManager] = None


def init_capture_manager(
    camera_manager: 'CameraManager',
    rgm_stream: Optional['RGMThermalStream'] = None
) -> CaptureManager:
    """Initialize the global capture manager instance."""
    global capture_manager
    capture_manager = CaptureManager(
        camera_manager=camera_manager,
        rgm_stream=rgm_stream
    )
    return capture_manager


def get_capture_manager() -> Optional[CaptureManager]:
    """Get the global capture manager instance."""
    return capture_manager


__all__ = [
    'CaptureManager',
    'capture_manager',
    'init_capture_manager',
    'get_capture_manager'
]

