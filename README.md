# GeoVision Camera Toolkit

Modular utilities for working with GeoVision dual RGB and thermal IP cameras.

## Structure

- `geovision/` – Core Python package
  - `config.py` – Shared configuration and credential helpers
  - `streams.py` – Threaded RTSP capture abstractions
  - `temperature.py` – HTTP API helpers for temperature queries
  - `overlay.py` – Drawing helpers for OpenCV overlays
- `app.py` – Flask application serving RGB and thermal streams side by side
- `temp_test.py` – Interactive thermal viewer with click-to-measure functionality
- `record_test.py` – Dual stream viewer with optional recording support
- `demo.py` – Minimal RGB stream viewer example

## Usage

1. Install dependencies:

   ```bash
   pip install -r requirements.txt
   ```

2. Configure credentials (defaults can be overridden with environment variables):

   ```bash
   export GEOVISION_IP="192.168.0.10"
   export GEOVISION_USER="admin"
   export GEOVISION_PASS="admin123"
   export GEOVISION_RGB_PROFILE="profile1"
   export GEOVISION_THERMAL_PROFILE="profile4"
   ```

3. Run the Flask web viewer:

   ```bash
   python app.py
   ```

   Visit `http://localhost:8000` to see both streams side by side.

4. Run the interactive thermal viewer:

   ```bash
   python temp_test.py
   ```

5. Record RGB and thermal streams:

   ```bash
   python record_test.py
   ```

## Notes

- The Flask app exposes `/video/rgb` and `/video/thermal` MJPEG endpoints
  suitable for embedding in dashboards.
- OpenCV connections are forced over TCP by default for reliability.
- Temperature utilities talk to the camera's HTTP API and return values in °C.
