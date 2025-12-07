# GeoVision Multi-Camera Stream Viewer

A Flask-based web application for monitoring **multiple GeoVision IP cameras** (RGB + thermal) alongside a local RGM thermal sensor, with real-time temperature measurement.

## Features

- **Multi-Camera Support**: Add, remove, and manage multiple GeoVision cameras
- **Dual Streams per Camera**: RGB and thermal video feeds from each IP camera
- **Interactive Temperature Measurement**: Click anywhere on thermal streams to measure temperature
- **Real-time MJPEG Streaming**: Low-latency video feeds in web browser
- **Dynamic Configuration**: Add/remove cameras through web interface without restart
- **Local RGM Thermal Camera**: USB-connected thermal imaging with center temperature display
- **Automatic Reconnection**: Handles network interruptions gracefully

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
├── static/
│   ├── css/style.css           # Styles
│   └── js/main.js              # Frontend logic
├── templates/
│   └── index.html              # Main page
├── requirements.txt            # Dependencies
└── README.md                   # This file
```




## Proposed Architecutre 
┌─────────────────┐     Serial      ┌──────────────────┐
│  AWR300 RFID    │ ─────────────▶ │  RFID Listener    |
│  Stick Reader   │                 │  (Background)    │
└─────────────────┘                 └────────┬─────────┘
                                             │
                                    Tag Scanned Event
                                             │
                                             ▼
┌────────────────────────────────────────────────────────────────┐
│                    Capture Manager                             │
│  1. Grab frame from GeoVision RGB stream                       │
│  2. Grab frame from GeoVision Thermal stream                   │
│  3. Grab frame from RGM stream                                 │
│  4. (Optional) Get temperature reading at center               │
│  5. Save frames to disk as JPEG files                          │
│  6. Log metadata + file paths to CSV                           │
└────────────────────────────────────────────────────────────────┘
                                             │
                                             ▼
┌────────────────────────────────────────────────────────────────┐
│  Storage Structure                                             │
│                                                                │
│  captures/                                                     │
│    ├── 2024-12-07_143045_982000123456789/                      │
│    │   ├── geovision_rgb.jpg                                   │
│    │   ├── geovision_thermal.jpg                               │
│    │   └── rgm_thermal.jpg                                     │
│    └── ...                                                     │
│                                                                │
│  cattle_captures.csv                                           │
│    ┌─────────────┬────────────┬────────┬──────────┬─────────┐  │
│    │ eid         │ timestamp  │ date   │ time     │ group   │  │
│    │ camera_id   │ rgb_path   │ therm  │ rgm_path │ temp_c  │  │
│    └─────────────┴────────────┴────────┴──────────┴─────────┘  │
└────────────────────────────────────────────────────────────────┘



## Technical Details

- **Backend**: Flask with threaded video capture
- **Video**: OpenCV with RTSP and MJPEG streaming
- **Temperature API**: GeoVision HTTP API with normalized coordinates
- **Frontend**: Vanilla JavaScript with dynamic DOM manipulation
- **State Management**: Server-side camera manager with thread-safe operations

## License

This project is provided as-is for educational and development purposes.
