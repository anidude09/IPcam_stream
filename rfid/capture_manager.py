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
        print(f"[CaptureManager] Data directory: {self.data_dir}")
        print(f"[CaptureManager] Captures directory: {self.captures_dir}")
    
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
            print(f"[CaptureManager] Created CSV file: {self.csv_file}")
        else:
            print(f"[CaptureManager] Using existing CSV: {self.csv_file}")
    
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
        
        print(f"\n[CaptureManager] ===== RFID CAPTURE =====")
        print(f"[CaptureManager] EID: {eid}")
        print(f"[CaptureManager] Timestamp: {timestamp}")
        print(f"[CaptureManager] Group: {group}")
        print(f"[CaptureManager] Folder: {capture_folder}")
        
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
        
        # Capture GeoVision frames
        if self.camera_manager:
            gv_result = self._capture_geovision_frames(
                capture_folder, camera_id
            )
            result.update(gv_result)
        else:
            result['errors'].append('No camera manager configured')
        
        # Capture RGM frame
        if self.rgm_stream:
            rgm_result = self._capture_rgm_frame(capture_folder)
            result.update(rgm_result)
        else:
            result['errors'].append('No RGM stream configured')
        
        # Get GeoVision temperature (center of frame)
        if self.camera_manager and result.get('camera_id') != 'none':
            temp_result = self._get_geovision_temperature(result['camera_id'])
            if temp_result is not None:
                result['geovision_temp_c'] = f"{temp_result:.2f}"
        
        # Get RGM temperature (center)
        if self.rgm_stream:
            rgm_temp = self._get_rgm_temperature()
            if rgm_temp is not None:
                result['rgm_temp_c'] = f"{rgm_temp:.2f}"
        
        # Log to CSV
        self._log_to_csv(result)
        
        result['success'] = len(result['errors']) == 0 or (
            result['rgb_frame_path'] or 
            result['thermal_frame_path'] or 
            result['rgm_frame_path']
        )
        
        print(f"[CaptureManager] Capture complete: success={result['success']}")
        print(f"[CaptureManager] ========================\n")
        
        return result
    
    def _capture_geovision_frames(
        self,
        capture_folder: Path,
        camera_id: Optional[str]
    ) -> Dict[str, str]:
        """Capture RGB and thermal frames from GeoVision camera."""
        result = {
            'rgb_frame_path': '',
            'thermal_frame_path': '',
            'camera_id': 'none'
        }
        
        # Get camera - either specified or first available
        if camera_id:
            managed = self.camera_manager.get_camera(camera_id)
        else:
            cameras = self.camera_manager.get_all_cameras()
            managed = cameras[0] if cameras else None
        
        if not managed:
            print("[CaptureManager] No GeoVision camera available")
            return result
        
        result['camera_id'] = managed.config.id
        
        # Capture RGB frame
        if managed.rgb_stream:
            rgb_frame = managed.rgb_stream.latest_frame(copy=True)
            if rgb_frame is not None:
                rgb_path = capture_folder / "geovision_rgb.jpg"
                if cv2.imwrite(str(rgb_path), rgb_frame):
                    # Store relative path from project root
                    result['rgb_frame_path'] = str(rgb_path.relative_to(Path.cwd()))
                    print(f"[CaptureManager] Saved RGB: {result['rgb_frame_path']}")
                else:
                    print("[CaptureManager] Failed to save RGB frame")
            else:
                print("[CaptureManager] No RGB frame available")
        
        # Capture Thermal frame
        if managed.thermal_stream:
            thermal_frame = managed.thermal_stream.latest_frame(copy=True)
            if thermal_frame is not None:
                thermal_path = capture_folder / "geovision_thermal.jpg"
                if cv2.imwrite(str(thermal_path), thermal_frame):
                    result['thermal_frame_path'] = str(thermal_path.relative_to(Path.cwd()))
                    print(f"[CaptureManager] Saved Thermal: {result['thermal_frame_path']}")
                else:
                    print("[CaptureManager] Failed to save thermal frame")
            else:
                print("[CaptureManager] No thermal frame available")
        
        return result
    
    def _capture_rgm_frame(self, capture_folder: Path) -> Dict[str, str]:
        """Capture frame from RGM thermal camera."""
        result = {'rgm_frame_path': ''}
        
        rgm_frame = self.rgm_stream.latest_frame(copy=True)
        if rgm_frame is not None:
            rgm_path = capture_folder / "rgm_thermal.jpg"
            if cv2.imwrite(str(rgm_path), rgm_frame):
                result['rgm_frame_path'] = str(rgm_path.relative_to(Path.cwd()))
                print(f"[CaptureManager] Saved RGM: {result['rgm_frame_path']}")
            else:
                print("[CaptureManager] Failed to save RGM frame")
        else:
            print("[CaptureManager] No RGM frame available")
        
        return result
    
    def _get_geovision_temperature(self, camera_id: str) -> Optional[float]:
        """Get center temperature from GeoVision thermal camera."""
        try:
            managed = self.camera_manager.get_camera(camera_id)
            if not managed:
                return None
            
            # Get center coordinates (5000, 5000 in normalized 0-10000 space)
            client = managed.get_temperature_client()
            result = client.get_dot_temperature(5000, 5000)
            
            if result:
                temp_c, _, _ = result
                print(f"[CaptureManager] GeoVision temp: {temp_c:.2f}°C")
                return temp_c
        except Exception as e:
            print(f"[CaptureManager] Error getting GeoVision temp: {e}")
        
        return None
    
    def _get_rgm_temperature(self) -> Optional[float]:
        """Get center temperature from RGM thermal camera."""
        try:
            center_data = self.rgm_stream.latest_center()
            if center_data and 'temp_c' in center_data:
                temp_c = center_data['temp_c']
                if temp_c is not None:
                    print(f"[CaptureManager] RGM temp: {temp_c:.2f}°C")
                    return temp_c
        except Exception as e:
            print(f"[CaptureManager] Error getting RGM temp: {e}")
        
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
            print(f"[CaptureManager] Logged to CSV: {self.csv_file}")
        except Exception as e:
            print(f"[CaptureManager] CSV write error: {e}")
    
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

