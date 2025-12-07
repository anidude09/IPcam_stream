"""
RFID Listener - Monitors AWR300 RFID reader via serial port.
Triggers frame captures when tags are scanned.
"""
from __future__ import annotations

import os
import threading
import time
from typing import Optional, Callable, List, TYPE_CHECKING

import serial
from serial.tools import list_ports

if TYPE_CHECKING:
    from .capture_manager import CaptureManager


# Default configuration (can be overridden by environment variables)
DEFAULT_BAUDRATE = 9600
DEFAULT_TIMEOUT = 1.0


class RFIDListener:
    """
    Listens for RFID tag scans from AWR300 reader and triggers captures.
    Runs as a background thread.
    """
    
    def __init__(
        self,
        port: Optional[str] = None,
        baudrate: int = DEFAULT_BAUDRATE,
        timeout: float = DEFAULT_TIMEOUT,
        capture_manager: Optional['CaptureManager'] = None,
        group: str = "default"
    ):
        """
        Initialize RFID listener.
        
        Args:
            port: Serial port (e.g., 'COM3' on Windows, '/dev/ttyUSB0' on Linux)
                  If None, will try to auto-detect AWR300.
            baudrate: Serial baudrate (default 9600 for AWR300)
            timeout: Read timeout in seconds
            capture_manager: CaptureManager instance for triggering captures
            group: Default group name for captures
        """
        self.port = port or os.environ.get('RFID_PORT')
        self.baudrate = baudrate
        self.timeout = timeout
        self.capture_manager = capture_manager
        self.group = group
        
        self._serial: Optional[serial.Serial] = None
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._callbacks: List[Callable[[str], None]] = []
        self._lock = threading.Lock()
        
        # Track recent scans to prevent duplicates
        self._recent_scans: dict = {}
        self._duplicate_timeout = 3.0  # seconds
    
    def add_callback(self, callback: Callable[[str], None]) -> None:
        """Add a callback to be called when a tag is scanned."""
        with self._lock:
            self._callbacks.append(callback)
    
    def remove_callback(self, callback: Callable[[str], None]) -> None:
        """Remove a callback."""
        with self._lock:
            if callback in self._callbacks:
                self._callbacks.remove(callback)
    
    def set_group(self, group: str) -> None:
        """Set the group name for captures."""
        self.group = group
        print(f"[RFIDListener] Group set to: {group}")
    
    @staticmethod
    def list_ports() -> List[dict]:
        """List available serial ports."""
        ports = []
        for port in list_ports.comports():
            ports.append({
                'device': port.device,
                'description': port.description,
                'manufacturer': port.manufacturer
            })
        return ports
    
    @staticmethod
    def find_awr300() -> Optional[str]:
        """Try to find AWR300 serial port automatically."""
        for port in list_ports.comports():
            # AWR300 typically shows up with "AWR300" in description or manufacturer
            if 'AWR300' in (port.description or '') or 'AWR300' in (port.manufacturer or ''):
                print(f"[RFIDListener] Found AWR300 at: {port.device}")
                return port.device
            # Also check for generic USB serial
            if 'USB' in (port.description or '').upper():
                print(f"[RFIDListener] Possible AWR300 at: {port.device} ({port.description})")
        return None
    
    def connect(self) -> bool:
        """Connect to the RFID reader."""
        if self._serial and self._serial.is_open:
            return True
        
        # Try to find port if not specified
        if not self.port:
            self.port = self.find_awr300()
        
        if not self.port:
            print("[RFIDListener] No RFID port specified and auto-detect failed")
            print("[RFIDListener] Available ports:")
            for p in self.list_ports():
                print(f"  - {p['device']}: {p['description']}")
            return False
        
        try:
            self._serial = serial.Serial(
                port=self.port,
                baudrate=self.baudrate,
                timeout=self.timeout
            )
            print(f"[RFIDListener] Connected to {self.port} at {self.baudrate} baud")
            return True
        except serial.SerialException as e:
            print(f"[RFIDListener] Failed to connect to {self.port}: {e}")
            return False
    
    def disconnect(self) -> None:
        """Disconnect from the RFID reader."""
        if self._serial:
            try:
                self._serial.close()
            except Exception:
                pass
            self._serial = None
            print("[RFIDListener] Disconnected from RFID reader")
    
    def start(self) -> bool:
        """Start listening for RFID scans in background thread."""
        if self._running:
            print("[RFIDListener] Already running")
            return True
        
        if not self.connect():
            return False
        
        self._running = True
        self._thread = threading.Thread(target=self._listen_loop, daemon=True)
        self._thread.start()
        print("[RFIDListener] Started listening for RFID scans")
        return True
    
    def stop(self) -> None:
        """Stop listening and close connection."""
        self._running = False
        if self._thread:
            self._thread.join(timeout=2.0)
            self._thread = None
        self.disconnect()
        print("[RFIDListener] Stopped")
    
    def is_running(self) -> bool:
        """Check if listener is running."""
        return self._running and self._thread is not None and self._thread.is_alive()
    
    def _listen_loop(self) -> None:
        """Main listening loop (runs in background thread)."""
        while self._running:
            try:
                if not self._serial or not self._serial.is_open:
                    print("[RFIDListener] Serial port closed, reconnecting...")
                    if not self.connect():
                        time.sleep(5.0)
                        continue
                
                # Read line from serial
                line = self._serial.readline()
                if not line:
                    continue
                
                # Decode and clean
                text = line.decode('ascii', errors='ignore').strip()
                if not text:
                    continue
                
                # Check for duplicate scan
                if self._is_duplicate(text):
                    continue
                
                print(f"\n[RFIDListener] Tag scanned: {text}")
                
                # Trigger capture
                self._handle_scan(text)
                
            except serial.SerialException as e:
                print(f"[RFIDListener] Serial error: {e}")
                self.disconnect()
                time.sleep(2.0)
            except Exception as e:
                print(f"[RFIDListener] Error in listen loop: {e}")
                time.sleep(0.5)
    
    def _is_duplicate(self, eid: str) -> bool:
        """Check if this is a duplicate scan (same tag within timeout)."""
        now = time.time()
        
        # Clean old entries
        self._recent_scans = {
            k: v for k, v in self._recent_scans.items()
            if now - v < self._duplicate_timeout
        }
        
        if eid in self._recent_scans:
            return True
        
        self._recent_scans[eid] = now
        return False
    
    def _handle_scan(self, eid: str) -> None:
        """Handle a tag scan - trigger capture and callbacks."""
        # Trigger capture if manager available
        if self.capture_manager:
            try:
                result = self.capture_manager.capture_on_rfid_scan(
                    eid=eid,
                    group=self.group
                )
                if result.get('success'):
                    print(f"[RFIDListener] Capture successful for {eid}")
                else:
                    print(f"[RFIDListener] Capture had issues: {result.get('errors', [])}")
            except Exception as e:
                print(f"[RFIDListener] Capture error: {e}")
        
        # Call registered callbacks
        with self._lock:
            for callback in self._callbacks:
                try:
                    callback(eid)
                except Exception as e:
                    print(f"[RFIDListener] Callback error: {e}")
    
    def manual_trigger(self, eid: str) -> dict:
        """
        Manually trigger a capture (for testing or API use).
        
        Args:
            eid: Tag ID to use
            
        Returns:
            Capture result dictionary
        """
        print(f"[RFIDListener] Manual trigger for EID: {eid}")
        
        if not self.capture_manager:
            return {'success': False, 'errors': ['No capture manager']}
        
        try:
            return self.capture_manager.capture_on_rfid_scan(
                eid=eid,
                group=self.group
            )
        except Exception as e:
            return {'success': False, 'errors': [str(e)]}


# Singleton instance (initialized by app.py)
rfid_listener: Optional[RFIDListener] = None


def init_rfid_listener(
    capture_manager: 'CaptureManager',
    port: Optional[str] = None,
    group: str = "default",
    auto_start: bool = False
) -> RFIDListener:
    """Initialize the global RFID listener instance."""
    global rfid_listener
    rfid_listener = RFIDListener(
        port=port,
        capture_manager=capture_manager,
        group=group
    )
    if auto_start:
        rfid_listener.start()
    return rfid_listener


def get_rfid_listener() -> Optional[RFIDListener]:
    """Get the global RFID listener instance."""
    return rfid_listener


__all__ = [
    'RFIDListener',
    'rfid_listener',
    'init_rfid_listener',
    'get_rfid_listener'
]

