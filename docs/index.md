# GeoVision Camera Toolkit — Documentation

Welcome to the **GeoVision Camera Toolkit** documentation.  
This project is a Flask-based multi-stream viewer and analysis platform built for GeoVision RGB/thermal IP cameras, with optional support for a local RGM USB thermal sensor, ArUco marker tracking, and YOLO-powered barcode detection.

![Web UI](../image.png)

---

## Documentation Map

| Document | What you'll find |
|---|---|
| [Camera Setup](camera-setup.md) | First-time GeoVision camera wiring, network discovery, RTSP profile configuration, and thermal API enablement |
| [Installation](installation.md) | Python prerequisites, virtual environment, and dependency installation |
| [Quick Start](quick-start.md) | Go from zero to a running dashboard in under two minutes |
| [Web UI Guide](web-ui-guide.md) | Walkthrough of every pane in the browser dashboard |
| [Configuration Reference](configuration.md) | Comprehensive table of every environment variable the app reads |
| [Architecture](architecture.md) | High-level system design, detailed camera protocol internals, and module-by-module code breakdown |
| [API Reference](api-reference.md) | Every HTTP endpoint with request/response examples |
| [Helper Scripts](helper-scripts.md) | Standalone utilities for testing, recording, and debugging |
| [Troubleshooting](troubleshooting.md) | Common issues, error messages, and their fixes |

---

## Quick Links

```
# Start the app
python app.py            # → http://localhost:8000

# Test camera connectivity
python demo.py           # RGB-only OpenCV window

# Interactive thermal debugging
python temp_test.py      # Click-to-measure thermal viewer
```

---

## License

[MIT](../LICENSE) — Copyright (c) 2025 Aniruddh
