# GeoVision Camera Toolkit

Modular utilities for GeoVision dual RGB and thermal IP cameras.

## Quick Start

```bash
# Install dependencies
pip install -r requirements.txt

# Configure camera credentials (optional - defaults provided)
export GEOVISION_IP="192.168.0.10"
export GEOVISION_USER="admin"
export GEOVISION_PASS="admin123"

# Run web viewer
python app.py
# Visit http://localhost:8000
```

## Functionalities

### Web Viewer (`app.py`)
- **Dual stream display**: RGB and thermal streams side by side
- **RGM thermal stream**: Optional USB/HDMI thermal feed rendered next to GeoVision streams
- **Temperature measurement**: Click on thermal stream to measure temperature
- **Auto-refresh**: Temperature updates every 1 second
- **Origin measurement**: Automatically measures at (0,0) on page load
- **Credential form**: Update GeoVision IP/username/password from the UI to restart streams without editing env vars

**Access**: `python app.py` → `http://localhost:8000`

### Interactive Thermal Viewer (`temp_test.py`)
- **Click-to-measure**: Click anywhere on thermal stream for temperature
- **Real-time updates**: Temperature refreshes automatically
- **Visual feedback**: Crosshair and temperature overlay

**Access**: `python temp_test.py`

### Dual Stream Recorder (`record_test.py`)
- **Simultaneous recording**: Record both RGB and thermal streams
- **Interactive controls**: Press 'r' to start/stop, 'q' to quit
- **Timestamped files**: Saves to `rgb_YYYYMMDD_HHMMSS.avi` and `thermal_YYYYMMDD_HHMMSS.avi`

**Access**: `python record_test.py`

### Temperature API Test (`temperature_api_test.py`)
- **API testing**: Test camera temperature API endpoints
- **ROI statistics**: Get min/max/avg temperature for configured regions
- **Dot temperature**: Test point temperature measurement

**Access**: `python temperature_api_test.py`

### Simple RGB Viewer (`demo.py`)
- **Basic stream viewer**: Minimal RGB stream display

**Access**: `python demo.py`

### RGM Thermal Stream (Integrated)
- **Local camera feed**: Opens a Windows-friendly backend (DirectShow/MSMF) for USB/HDMI thermal sensors
- **Center-point temperature**: Displays Celsius/Fahrenheit reading for the center pixel
- **Colorized output**: Applies an Inferno colormap with adjustable temperature window

## Configuration

Set environment variables to override defaults:
- `GEOVISION_IP` - Camera IP address (default: 192.168.0.10)
- `GEOVISION_USER` - Username (default: admin)
- `GEOVISION_PASS` - Password (default: admin123)
- `GEOVISION_RGB_PROFILE` - RGB stream profile (default: profile1)
- `GEOVISION_THERMAL_PROFILE` - Thermal stream profile (default: profile4)
- `RGM_DEVICE_INDEX` - Local camera index (default: 0)
- `RGM_USE_MSMF` - Use MSMF backend instead of DirectShow (`true`/`false`, default: false)
- `RGM_VIEW_SCALE` - Upscale factor for display (default: 3)
- `RGM_TEMP_MIN_C` / `RGM_TEMP_MAX_C` - Temperature window for colorization (defaults: 20 / 40)
