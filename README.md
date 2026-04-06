# GeoVision Camera Toolkit

A Flask-based multi-stream viewer and analysis platform for GeoVision RGB/thermal IP cameras — with temperature measurement, ArUco marker tracking, YOLO barcode detection, and local RGM thermal sensor support.

![Web UI](image.png)

---

## Features

| Feature | Description |
|---|---|
| **RGB & Thermal Streaming** | Live MJPEG streams from GeoVision camera's RGB and thermal sensors |
| **Click-to-Measure Temperature** | Click any pixel on the thermal feed to query the camera's per-pixel temperature API |
| **ArUco Marker Tracking** | Real-time detection and motion trail visualization for ArUco fiducial markers |
| **Barcode Detection** | YOLOv8-powered barcode region detection with optional multi-library decoding |
| **RGM USB Thermal Sensor** | Secondary thermal feed from a local USB thermal camera with center-point readout |
| **Runtime Configuration** | Change camera credentials in the browser without restarting the app |

---

## Quick Start

```powershell
cd C:\Users\aniruddh\IPcam_stream
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt

# Set camera credentials (or configure in the web UI later)
$env:GEOVISION_IP = "192.168.0.10"
$env:GEOVISION_USER = "admin"
$env:GEOVISION_PASS = "admin123"

python app.py
# → http://localhost:8000
```

---

## Documentation

Full documentation lives in the [`docs/`](docs/index.md) directory:

| Document | Description |
|---|---|
| [**Camera Setup**](docs/camera-setup.md) | First-time GeoVision camera wiring, network discovery, RTSP profiles, and thermal API enablement |
| [**Installation**](docs/installation.md) | Python prerequisites, virtual environment, and dependency installation |
| [**Quick Start**](docs/quick-start.md) | From zero to a running dashboard in under two minutes |
| [**Web UI Guide**](docs/web-ui-guide.md) | Walkthrough of every pane in the browser dashboard |
| [**Configuration**](docs/configuration.md) | Complete reference for all  environment variables |
| [**Architecture**](docs/architecture.md) | System design, camera protocols (RTSP, HTTP temperature API), and module-by-module code breakdown |
| [**API Reference**](docs/api-reference.md) | Every HTTP endpoint with request/response examples |
| [**Helper Scripts**](docs/helper-scripts.md) | Standalone tools for testing, recording, and debugging |
| [**Troubleshooting**](docs/troubleshooting.md) | Common issues and their fixes |

---

## Helper Scripts

```powershell
python demo.py                  # Simple RGB-only viewer (quickest connectivity test)
python temp_test.py             # Interactive thermal viewer with click-to-measure
python record_test.py           # Dual-stream (RGB + thermal) AVI recorder
python temperature_api_test.py  # CLI probe of the GeoVision temperature HTTP API
```

---

## Project Structure

```
IPcam_stream/
├── app.py                      # Main Flask application (port 8000)
├── barcode_service.py          # Separate barcode detection process (port 8100)
├── geovision/                  # GeoVision camera package (RTSP, temp API, ArUco, barcode)
├── rgm/                        # RGM USB thermal sensor package
├── yolo_barcode_package/       # YOLOv8 barcode detection + decoding engine
├── templates/                  # Jinja2 HTML template
├── static/                     # CSS + JavaScript
├── docs/                       # Full documentation
├── demo.py                     # RGB viewer
├── temp_test.py                # Thermal viewer
├── record_test.py              # Dual-stream recorder
└── temperature_api_test.py     # Temperature API tester
```

---

## License

[MIT](LICENSE) — Copyright (c) 2025 Aniruddh
