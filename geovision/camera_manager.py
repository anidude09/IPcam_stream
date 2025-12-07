"""
Multi-camera manager for GeoVision cameras.
Handles multiple camera configurations and their streams.
"""
from __future__ import annotations

import threading
import uuid
from dataclasses import dataclass
from typing import Dict, List, Optional

from .config import CameraCredentials, RGB_STREAM, THERMAL_STREAM, StreamProfile
from .streams import RTSPStream
from .temperature import TemperatureClient


@dataclass
class CameraConfig:
    """Configuration for a single GeoVision camera."""
    id: str
    name: str
    ip_address: str
    username: str
    password: str
    enabled: bool = True
    
    def to_credentials(self) -> CameraCredentials:
        """Convert to CameraCredentials for API calls."""
        return CameraCredentials(
            ip_address=self.ip_address,
            username=self.username,
            password=self.password
        )
    
    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "id": self.id,
            "name": self.name,
            "ip_address": self.ip_address,
            "username": self.username,
            "enabled": self.enabled
        }


@dataclass
class ManagedCamera:
    """A camera with its associated streams."""
    config: CameraConfig
    rgb_stream: Optional[RTSPStream] = None
    thermal_stream: Optional[RTSPStream] = None
    
    def start_streams(self) -> None:
        """Start RGB and thermal streams for this camera."""
        credentials = self.config.to_credentials()
        
        # Create and start RGB stream
        self.rgb_stream = RTSPStream(
            credentials=credentials,
            profile=RGB_STREAM,
            name=f"{self.config.name}-RGB"
        )
        self.rgb_stream.start()
        
        # Create and start thermal stream
        self.thermal_stream = RTSPStream(
            credentials=credentials,
            profile=THERMAL_STREAM,
            name=f"{self.config.name}-Thermal"
        )
        self.thermal_stream.start()
        
        print(f"[CameraManager] Started streams for camera: {self.config.name} ({self.config.ip_address})")
    
    def stop_streams(self) -> None:
        """Stop all streams for this camera."""
        if self.rgb_stream:
            self.rgb_stream.stop()
            self.rgb_stream = None
        if self.thermal_stream:
            self.thermal_stream.stop()
            self.thermal_stream = None
        print(f"[CameraManager] Stopped streams for camera: {self.config.name}")
    
    def get_temperature_client(self) -> TemperatureClient:
        """Get a temperature client for this camera."""
        return TemperatureClient(
            credentials=self.config.to_credentials(),
            channel=THERMAL_STREAM.channel
        )


class CameraManager:
    """
    Manages multiple GeoVision cameras.
    Thread-safe operations for adding, removing, and accessing cameras.
    """
    
    def __init__(self):
        self._cameras: Dict[str, ManagedCamera] = {}
        self._lock = threading.Lock()
    
    def add_camera(
        self,
        name: str,
        ip_address: str,
        username: str,
        password: str,
        camera_id: Optional[str] = None,
        start_streams: bool = True
    ) -> CameraConfig:
        """
        Add a new camera to the manager.
        
        Args:
            name: Display name for the camera
            ip_address: Camera IP address
            username: Camera username
            password: Camera password
            camera_id: Optional custom ID, auto-generated if not provided
            start_streams: Whether to start streams immediately
            
        Returns:
            The created CameraConfig
        """
        with self._lock:
            # Generate ID if not provided
            if camera_id is None:
                camera_id = str(uuid.uuid4())[:8]
            
            # Check for duplicate ID
            if camera_id in self._cameras:
                raise ValueError(f"Camera with ID '{camera_id}' already exists")
            
            # Create config
            config = CameraConfig(
                id=camera_id,
                name=name,
                ip_address=ip_address,
                username=username,
                password=password
            )
            
            # Create managed camera
            managed = ManagedCamera(config=config)
            
            # Start streams if requested
            if start_streams:
                try:
                    managed.start_streams()
                except Exception as e:
                    print(f"[CameraManager] Failed to start streams for {name}: {e}")
                    # Still add the camera but mark it as having issues
            
            self._cameras[camera_id] = managed
            print(f"[CameraManager] Added camera: {name} (ID: {camera_id})")
            
            return config
    
    def remove_camera(self, camera_id: str) -> bool:
        """
        Remove a camera from the manager.
        
        Args:
            camera_id: ID of the camera to remove
            
        Returns:
            True if camera was removed, False if not found
        """
        with self._lock:
            if camera_id not in self._cameras:
                return False
            
            managed = self._cameras[camera_id]
            managed.stop_streams()
            del self._cameras[camera_id]
            
            print(f"[CameraManager] Removed camera: {managed.config.name}")
            return True
    
    def get_camera(self, camera_id: str) -> Optional[ManagedCamera]:
        """Get a camera by ID."""
        with self._lock:
            return self._cameras.get(camera_id)
    
    def get_all_cameras(self) -> List[ManagedCamera]:
        """Get all managed cameras."""
        with self._lock:
            return list(self._cameras.values())
    
    def get_camera_configs(self) -> List[dict]:
        """Get configurations of all cameras as dictionaries."""
        with self._lock:
            return [cam.config.to_dict() for cam in self._cameras.values()]
    
    def update_camera(
        self,
        camera_id: str,
        name: Optional[str] = None,
        ip_address: Optional[str] = None,
        username: Optional[str] = None,
        password: Optional[str] = None
    ) -> Optional[CameraConfig]:
        """
        Update camera configuration. Restarts streams if connection details change.
        
        Returns:
            Updated CameraConfig or None if camera not found
        """
        with self._lock:
            if camera_id not in self._cameras:
                return None
            
            managed = self._cameras[camera_id]
            old_config = managed.config
            
            # Check if connection details changed
            connection_changed = (
                (ip_address and ip_address != old_config.ip_address) or
                (username and username != old_config.username) or
                (password and password != old_config.password)
            )
            
            # Create new config with updates
            new_config = CameraConfig(
                id=camera_id,
                name=name or old_config.name,
                ip_address=ip_address or old_config.ip_address,
                username=username or old_config.username,
                password=password if password is not None else old_config.password,
                enabled=old_config.enabled
            )
            
            managed.config = new_config
            
            # Restart streams if connection details changed
            if connection_changed:
                managed.stop_streams()
                try:
                    managed.start_streams()
                except Exception as e:
                    print(f"[CameraManager] Failed to restart streams: {e}")
            
            return new_config
    
    def shutdown(self) -> None:
        """Stop all streams and clean up."""
        with self._lock:
            for managed in self._cameras.values():
                managed.stop_streams()
            self._cameras.clear()
            print("[CameraManager] All cameras shut down")


# Global camera manager instance
camera_manager = CameraManager()


__all__ = [
    "CameraConfig",
    "ManagedCamera", 
    "CameraManager",
    "camera_manager"
]

