# GeoVision IP Camera Stream Viewer

A Flask-based web application for monitoring GeoVision RGB/thermal IP cameras alongside local RGM thermal sensors with real-time temperature measurement capabilities.

## Features

- **Dual GeoVision Streams**: RGB and thermal video feeds from IP cameras
- **Local RGM Thermal Camera**: USB-connected thermal imaging with center temperature display
- **Interactive Temperature Measurement**: Click anywhere on thermal streams to measure temperature
- **Real-time MJPEG Streaming**: Low-latency video feeds in web browser
- **Dynamic Configuration**: Update camera settings through web interface
- **Automatic Reconnection**: Handles network interruptions gracefully

## Hardware Requirements

### GeoVision IP Camera
- GeoVision IP camera with dual streams (RGB + thermal)
- Network connectivity (Ethernet/WiFi)
- RTSP streaming enabled
- HTTP API access for temperature measurements

### RGM Thermal Camera
- USB-connected thermal camera (typically device index 0)
- Compatible with Windows DirectShow or MSMF backends
- Raw thermal data output capability

### System Requirements
- Windows 10/11 laptop or desktop
- USB ports for RGM camera connection
- Network access to GeoVision camera
- Python 3.8+ (included in setup)

## Installation & Setup

### 1. Clone/Download the Project
```powershell
# Create project directory
mkdir IPcam_stream
cd IPcam_stream
# Copy all project files here
```

### 2. Set Up Python Virtual Environment
```powershell
# Create virtual environment
python -m venv .venv

# Activate virtual environment
.\.venv\Scripts\Activate.ps1

# Install dependencies
pip install -r requirements.txt
```

### 3. Configure Camera Settings (Optional)
Set environment variables before starting, or configure via web interface:

```powershell
# GeoVision Camera Settings
$env:GEOVISION_IP="192.168.1.100"      # Your camera's IP address
$env:GEOVISION_USER="admin"            # Camera username
$env:GEOVISION_PASS="your_password"    # Camera password

# RGM Camera Settings (optional)
$env:RGM_DEVICE_INDEX="0"              # USB camera device index
$env:RGM_USE_MSMF="false"              # Use MSMF backend (true/false)
$env:RGM_VIEW_SCALE="3"                # Display scaling factor
$env:RGM_TEMP_MIN_C="20.0"             # Min temperature for color scale
$env:RGM_TEMP_MAX_C="40.0"             # Max temperature for color scale
```

### 4. Start the Application
```powershell
python app.py
```

### 5. Access the Web Interface
Open your browser and navigate to: **http://localhost:8000**

## Usage Guide

### Web Interface Overview
- **GeoVision RGB**: Live RGB video feed
- **GeoVision Thermal**: Thermal imaging with click-to-measure temperature
- **RGM Thermal**: Local USB thermal camera with center temperature display

### Temperature Measurement
1. Click anywhere on the GeoVision thermal stream
2. A green crosshair appears at the clicked location
3. Temperature reading updates in real-time
4. Measurements refresh automatically every second

### Camera Configuration
- Use the "GeoVision Camera Settings" form to update IP address, username, and password
- Changes take effect immediately and streams restart automatically
- RGM settings require environment variable changes and application restart

## Network & Firewall Configuration

### Required Network Access
- **RTSP Port 554**: For video streaming from GeoVision camera
- **HTTP Port 80**: For temperature API calls to GeoVision camera
- **Local Port 8000**: Web application (automatically opened)

### Windows Firewall
The application will prompt for firewall access when first started. Allow access for:
- Python executable
- Application network communications

### Camera Network Setup
Ensure your GeoVision camera:
- Is on the same network as your laptop
- Has RTSP streaming enabled
- Has HTTP API access enabled
- Firewall allows connections from your laptop's IP

## Troubleshooting

### GeoVision Camera Connection Issues
```powershell
# Test basic connectivity
ping YOUR_CAMERA_IP

# Verify RTSP stream URL format
# Should be: rtsp://username:password@ip_address:554/profile1
```

**Common Solutions:**
- Check camera IP address and network connectivity
- Verify username/password credentials
- Ensure RTSP is enabled in camera settings
- Check firewall settings on both camera and laptop

### RGM Camera Not Detected
```powershell
# List available camera devices (run in Python)
import cv2
for i in range(10):
    cap = cv2.VideoCapture(i)
    if cap.isOpened():
        print(f"Camera found at index {i}")
    cap.release()
```

**Common Solutions:**
- Try different device indices (0, 1, 2, etc.)
- Switch between DirectShow and MSMF backends
- Ensure USB cable is properly connected
- Check device manager for camera driver issues

### Application Won't Start
- Ensure virtual environment is activated
- Verify all dependencies are installed: `pip list`
- Check Python version: `python --version` (requires 3.8+)
- Look for error messages in console output

### Performance Issues
- Close other camera applications
- Reduce RGM_VIEW_SCALE for better performance
- Ensure stable network connection to GeoVision camera
- Check CPU usage - thermal processing is CPU intensive

## Configuration Reference

### GeoVision Camera Settings
| Variable | Default | Description |
|----------|---------|-------------|
| `GEOVISION_IP` | `192.168.0.10` | Camera IP address |
| `GEOVISION_USER` | `admin` | Camera username |
| `GEOVISION_PASS` | `admin123` | Camera password |
| `GEOVISION_RGB_PROFILE` | `profile1` | RGB stream profile ID |
| `GEOVISION_THERMAL_PROFILE` | `profile4` | Thermal stream profile ID |

### RGM Camera Settings
| Variable | Default | Description |
|----------|---------|-------------|
| `RGM_DEVICE_INDEX` | `0` | USB camera device index |
| `RGM_USE_MSMF` | `false` | Use MSMF instead of DirectShow |
| `RGM_VIEW_SCALE` | `3` | Display scaling factor |
| `RGM_TEMP_MIN_C` | `20.0` | Minimum temperature (°C) |
| `RGM_TEMP_MAX_C` | `40.0` | Maximum temperature (°C) |

## Technical Details

- **Backend**: Flask web framework with threaded video capture
- **Video Processing**: OpenCV with RTSP and USB camera support
- **Temperature API**: HTTP-based GeoVision camera API
- **Streaming**: MJPEG over HTTP for real-time video
- **Frontend**: Vanilla JavaScript with responsive CSS

## Support

For issues with:
- **GeoVision cameras**: Check camera firmware and network configuration
- **RGM cameras**: Verify USB connection and driver installation
- **Application**: Check console output for error messages and logs

## License

This project is provided as-is for educational and development purposes.