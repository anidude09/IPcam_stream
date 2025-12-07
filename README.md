# GeoVision Multi-Camera Stream Viewer with RFID Capture

A Flask-based web application for monitoring **multiple GeoVision IP cameras** (RGB + thermal) alongside a local RGM thermal sensor, with real-time temperature measurement and **RFID-triggered frame capture** for cattle identification.

## Features

- **Multi-Camera Support**: Add, remove, and manage multiple GeoVision cameras
- **Dual Streams per Camera**: RGB and thermal video feeds from each IP camera
- **Interactive Temperature Measurement**: Click anywhere on thermal streams to measure temperature
- **Real-time MJPEG Streaming**: Low-latency video feeds in web browser
- **Dynamic Configuration**: Add/remove cameras through web interface without restart
- **Local RGM Thermal Camera**: USB-connected thermal imaging with center temperature display
- **Automatic Reconnection**: Handles network interruptions gracefully
- **RFID Capture System**: AWR300 RFID reader triggers automatic frame capture with temperature logging

## Quick Start

### 1. Setup Environment
```powershell
cd C:\Users\aniruddh\IPcam_stream
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

### 2. Run the Application
```powershell
python app.py
```

### 3. Open Browser
Navigate to: **http://localhost:8000**

### 4. Add Cameras
Use the "Add GeoVision Camera" form to add cameras:
- Enter a **name** (e.g., "Front Entrance")
- Enter the camera's **IP address**
- Enter **username** and **password**
- Click "Add Camera"

You can add multiple cameras - each will display its RGB and thermal streams.

## Optional: Pre-configure Default Camera

Set environment variables before starting to auto-add a camera:
```powershell
$env:GEOVISION_IP="192.168.1.100"
$env:GEOVISION_USER="admin"
$env:GEOVISION_PASS="your_password"
$env:GEOVISION_NAME="Main Camera"

python app.py
```

## API Reference

### Camera Management

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/cameras` | GET | List all cameras |
| `/api/cameras` | POST | Add a new camera |
| `/api/cameras/<id>` | PUT | Update camera settings |
| `/api/cameras/<id>` | DELETE | Remove a camera |

### Video Streams

| Endpoint | Description |
|----------|-------------|
| `/video/<camera_id>/rgb` | RGB video stream |
| `/video/<camera_id>/thermal` | Thermal video stream |
| `/video/rgm` | RGM local thermal stream |

### Temperature

| Endpoint | Description |
|----------|-------------|
| `/api/cameras/<id>/temperature?x=<x>&y=<y>` | Get temperature at coordinates |
| `/rgm/center_temperature` | Get RGM center temperature |

### RFID Capture

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/rfid/capture` | POST | Manual capture trigger (body: `{eid, group, notes}`) |
| `/api/rfid/status` | GET | Get RFID listener status |
| `/api/rfid/start` | POST | Start RFID listener (body: `{port}` optional) |
| `/api/rfid/stop` | POST | Stop RFID listener |
| `/api/rfid/group` | POST | Set capture group name (body: `{group}`) |
| `/api/rfid/ports` | GET | List available serial ports |

## Temperature Measurement

### How It Works
1. Click anywhere on a thermal stream
2. Coordinates are converted to GeoVision API format (0-10000 normalized)
3. Temperature is fetched from the camera's API
4. Reading updates automatically every second

### GeoVision API Coordinate System
The GeoVision temperature API uses **normalized coordinates (0-10000)**:
- `(0, 0)` = Top-left corner
- `(10000, 10000)` = Bottom-right corner
- `(5000, 5000)` = Center

## Troubleshooting

### Camera Won't Connect
- Verify IP address is correct and camera is on same network
- Check username/password credentials
- Ensure RTSP streaming is enabled on camera
- Check firewall settings

### Temperature Readings Incorrect
- The application now uses normalized coordinates (0-10000)
- Check browser console (F12) for coordinate debug info
- Verify camera's thermal API is functioning

### RGM Camera Not Detected
```powershell
# Try different device index
$env:RGM_DEVICE_INDEX="1"

# Or try MSMF backend
$env:RGM_USE_MSMF="true"
```

## Configuration Reference

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `GEOVISION_IP` | - | Default camera IP (optional) |
| `GEOVISION_USER` | `admin` | Default camera username |
| `GEOVISION_PASS` | `admin123` | Default camera password |
| `GEOVISION_NAME` | `GeoVision Camera` | Default camera display name |
| `RGM_DEVICE_INDEX` | `0` | USB camera device index |
| `RGM_USE_MSMF` | `false` | Use MSMF instead of DirectShow |
| `RGM_VIEW_SCALE` | `3` | Display scaling factor |
| `RGM_TEMP_MIN_C` | `20.0` | Min temperature for color scale |
| `RGM_TEMP_MAX_C` | `40.0` | Max temperature for color scale |
| `RFID_PORT` | - | Serial port for AWR300 (e.g., `COM3`) |
| `RFID_GROUP` | `default` | Default group name for captures |

## Project Structure

```
IPcam_stream/
├── app.py                      # Main Flask application
├── geovision/
│   ├── camera_manager.py       # Multi-camera management
│   ├── config.py               # Camera configuration
│   ├── streams.py              # RTSP streaming
│   ├── temperature.py          # Temperature API
│   └── overlay.py              # Drawing utilities
├── rgm/
│   ├── io.py                   # Camera I/O
│   ├── processing.py           # Thermal processing
│   └── streaming.py            # MJPEG streaming
├── rfid/
│   ├── capture_manager.py      # Frame capture and CSV logging
│   ├── listener.py             # AWR300 serial port listener
│   └── script.py               # Standalone RFID logger (legacy)
├── data/                       # Created automatically
│   ├── captures/               # Captured frame images
│   └── cattle_captures.csv     # Capture metadata log
├── static/
│   ├── css/style.css           # Styles
│   └── js/main.js              # Frontend logic
├── templates/
│   └── index.html              # Main page
├── requirements.txt            # Dependencies
└── README.md                   # This file
```




## RFID Capture System

### Overview

When an RFID tag is scanned with the AWR300 reader, the system automatically:
1. Captures frames from all active camera streams (GeoVision RGB, Thermal, RGM)
2. Measures center temperature from thermal cameras
3. Saves frames as JPEG files
4. Logs metadata to CSV with relative file paths

### Setup AWR300 RFID Reader

1. **Connect AWR300** to USB port
2. **Find the COM port**:
   - Open Device Manager → Ports (COM & LPT)
   - Look for "AWR300" or "USB Serial Device"
   - Note the COM port (e.g., `COM3`)

3. **Configure environment**:
```powershell
$env:RFID_PORT="COM3"
$env:RFID_GROUP="Session_2024_12_07"
python app.py
```



4. **Or start via API** (after app is running):
```powershell
# List available ports
curl http://localhost:8000/api/rfid/ports

# Start listener on specific port
curl -X POST http://localhost:8000/api/rfid/start -H "Content-Type: application/json" -d "{\"port\": \"COM3\"}"
```

### Manual Capture 

Trigger a capture without RFID reader:
```powershell
curl -X POST http://localhost:8000/api/rfid/capture -H "Content-Type: application/json" -d "{\"eid\": \"TEST123456\", \"group\": \"TestSession\"}"
```

### Output Structure

```
data/
├── captures/
│   └── 2024-12-07_143045_982000123456789/
│       ├── geovision_rgb.jpg
│       ├── geovision_thermal.jpg
│       └── rgm_thermal.jpg
└── cattle_captures.csv
```

### CSV Format

| Column | Description |
|--------|-------------|
| `eid` | Electronic ID from RFID tag |
| `timestamp` | ISO format timestamp |
| `date` | Date (YYYY-MM-DD) |
| `time` | Time (HH:MM:SS) |
| `group` | Session/group name |
| `camera_id` | GeoVision camera used |
| `rgb_frame_path` | Relative path to RGB frame |
| `thermal_frame_path` | Relative path to thermal frame |
| `rgm_frame_path` | Relative path to RGM frame |
| `geovision_temp_c` | Center temperature from GeoVision |
| `rgm_temp_c` | Center temperature from RGM |
| `notes` | Optional notes |



## Technical Details

- **Backend**: Flask with threaded video capture
- **Video**: OpenCV with RTSP and MJPEG streaming
- **Temperature API**: GeoVision HTTP API with normalized coordinates
- **Frontend**: Vanilla JavaScript with dynamic DOM manipulation
- **State Management**: Server-side camera manager with thread-safe operations

## License

This project is provided as-is for educational and development purposes.
