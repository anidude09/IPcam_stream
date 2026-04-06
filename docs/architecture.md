# Architecture

This document covers the **high-level system design**, **camera protocol details**, and a **module-by-module code breakdown**.

---

## System Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                        Browser (MJPEG)                          │
│  ┌──────────┐ ┌──────────┐ ┌──────┐ ┌───────┐ ┌───────────┐   │
│  │ RGB Pane │ │ Thermal  │ │ RGM  │ │ ArUco │ │  Barcode  │   │
│  │          │ │ + Click  │ │      │ │       │ │           │   │
│  └────┬─────┘ └────┬─────┘ └──┬───┘ └───┬───┘ └─────┬─────┘   │
│       │             │          │         │           │          │
└───────┼─────────────┼──────────┼─────────┼───────────┼──────────┘
        │             │          │         │           │
   /video/rgb   /video/thermal /video/rgm /video/aruco /video/barcode
        │             │          │         │           │
┌───────┴─────────────┴──────────┴─────────┴───────────┴──────────┐
│                     Flask Server (app.py :8000)                   │
│                                                                   │
│  ┌─────────────┐  ┌─────────────┐  ┌──────────────┐             │
│  │ RTSPStream  │  │ RTSPStream  │  │ ArucoStream  │             │
│  │ (RGB/preview)│  │ (Thermal)   │  │ (extends     │             │
│  │             │  │             │  │  RTSPStream)  │             │
│  └──────┬──────┘  └──────┬──────┘  └──────────────┘             │
│         │                │                                        │
│         │         ┌──────┴──────┐   ┌──────────────────────────┐ │
│         │         │ Temperature │   │ Barcode Service (:8100)  │ │
│         │         │ Client      │   │ ┌────────────────────┐   │ │
│         │         │ (HTTP/XML)  │   │ │ RTSPStream (full)  │   │ │
│         │         └──────┬──────┘   │ │ + BarcodeStream    │   │ │
│         │                │          │ │   (YOLOv8 + decode) │   │ │
│         │                │          │ └────────────────────┘   │ │
│  ┌──────┴────────────────┴──────┐   └──────────────────────────┘ │
│  │    RGMThermalStream          │                                 │
│  │    (USB camera, DirectShow)  │                                 │
│  └──────────────────────────────┘                                 │
└───────────────────────────────────────────────────────────────────┘
        │                │                    │
        ▼                ▼                    ▼
┌──────────────┐ ┌──────────────┐  ┌──────────────────┐
│ GeoVision    │ │ GeoVision    │  │ USB Thermal      │
│ Camera       │ │ Camera       │  │ Sensor (RGM)     │
│ RTSP :554    │ │ HTTP API :80 │  │ DirectShow/MSMF  │
└──────────────┘ └──────────────┘  └──────────────────┘
```

---

## Camera Communication — Detailed Protocol View

### RTSP Video Streaming

The GeoVision camera exposes multiple RTSP streams on **port 554** (standard RTSP port). The toolkit connects via OpenCV's FFmpeg backend using TCP transport.

```
                        RTSP/TCP
  ┌────────────┐    port 554     ┌────────────────────┐
  │ RTSPStream ├────────────────►│ GeoVision Camera   │
  │ (OpenCV    │                 │                    │
  │  FFmpeg    │  RTSP DESCRIBE  │  /profile1 (CH1)   │
  │  backend)  │  RTSP SETUP     │  /profile2 (CH1)   │
  │            │  RTSP PLAY      │  /profile4 (CH2)   │
  └────────────┘                 └────────────────────┘
```

**Connection lifecycle:**

1. `RTSPStream.start()` spawns a daemon thread running `_capture_loop()`
2. `_ensure_capture()` opens an `cv2.VideoCapture` with the RTSP URL
3. Transport is forced to TCP via the `OPENCV_FFMPEG_CAPTURE_OPTIONS` env var
4. Buffer size is set to 1 frame to minimize latency
5. Each `cap.read()` yields a decoded BGR `numpy` frame
6. The frame is stored as `_latest_frame` (protected by a lock)
7. If `read()` fails, the capture is released and reconnected after a configurable delay

**RTSP URL construction:**

```python
# CameraCredentials.rtsp_url()
f"rtsp://{username}:{password}@{ip_address}:554/{profile_id}"

# Example:
"rtsp://admin:admin123@192.168.0.10:554/profile2"
```

**Stream profiles used:**

| Profile | Channel | Sensor | Resolution | FPS | Usage |
|---------|---------|--------|------------|-----|-------|
| `profile1` | 1 | RGB | Full HD ~1920×1080 | 30 | Barcode service (needs max resolution) |
| `profile2` | 1 | RGB | Preview ~640×480 | 30 | Web UI RGB pane, ArUco detection |
| `profile4` | 2 | Thermal | ~384×288 | 15 | Thermal pane, temperature overlay |

### MJPEG Delivery to Browser

RTSP frames are re-encoded to JPEG and pushed to the browser as an MJPEG stream using Flask's streaming response:

```
RTSPStream._capture_loop()          Flask video route
┌─────────────────────┐           ┌────────────────────────┐
│ cap.read() → frame  │           │ mjpeg_generator():     │
│ _set_latest_frame() │──frame──► │  cv2.imencode('.jpg')  │
│ (background thread) │           │  yield multipart chunk │
└─────────────────────┘           └────────────────────────┘
                                          │
                                          ▼ HTTP
                                  ┌──────────────────┐
                                  │ Browser <img>    │
                                  │ src="/video/rgb" │
                                  └──────────────────┘
```

**MJPEG multipart format:**

```
--frame\r\n
Content-Type: image/jpeg\r\n\r\n
<JPEG bytes>\r\n
```

**Optimizations:**
- **Frame deduplication:** The same `frame_id` is never encoded twice. If a browser client polls faster than the camera, it busy-waits (2ms sleep) until a new frame arrives.
- **JPEG cache:** Encoded JPEG bytes are cached per quality level per frame ID, so multiple browser clients don't re-encode the same frame.
- **Downscale:** RGB preview frames wider than `RGB_PREVIEW_MAX_WIDTH` are downscaled server-side before encoding.

---

### HTTP Temperature API

The GeoVision camera exposes an HTTP API on **port 80** for temperature queries. This toolkit's `TemperatureClient` uses it.

```
                     HTTP POST + Basic Auth
  ┌──────────────────┐    port 80     ┌────────────────────┐
  │ TemperatureClient├───────────────►│ GeoVision Camera   │
  │                  │                │                    │
  │  POST /GetDot... │  XML request   │  Reads thermal     │
  │  GET /GetTemp... │  XML response  │  sensor at (x,y)   │
  └──────────────────┘                └────────────────────┘
```

**Dot temperature flow:**

```
1. Client sends POST request:
   URL:  http://192.168.0.10/GetDotTemperature/2
   Auth: Basic admin:admin123
   Body:
     <?xml version="1.0" encoding="UTF-8"?>
     <config version="1.0" xmlns="http://www.ipc.com/ver10">
       <dotTemperature>
         <hotX>192</hotX>
         <hotY>144</hotY>
       </dotTemperature>
     </config>

2. Camera responds with XML:
     <config ...>
       <dotTemperature>
         <temperature>2835</temperature>   ← raw value
         <hotX>192</hotX>                   ← confirmed coords
         <hotY>144</hotY>
       </dotTemperature>
     </config>

3. Client parses:
   temp_celsius = 2835 / 100.0 = 28.35 °C
```

**Temperature conversion:**
- Raw value is in **hundredths of a degree Celsius**
- The `temp_conversion_factor` (default 100.0) divides the raw value
- An optional `temp_offset` can be added for calibration

**ROI statistics flow:**

```
GET http://192.168.0.10/GetTemperatureCurrentInfo/2
Auth: Basic admin:admin123

Response contains <maxTemper>, <minTemper>, <avgTemper> nodes
Each value is also in hundredths of °C
```

---

### USB Thermal Sensor (RGM)

The RGM module is a separate local USB thermal camera (not the GeoVision):

```
  ┌──────────────────┐    USB     ┌────────────────────┐
  │ RGMThermalStream ├───────────►│ Thermal Sensor     │
  │                  │            │ (USB, 16-bit raw)  │
  │ DirectShow/MSMF  │            │ e.g. 80x60         │
  └──────────────────┘            └────────────────────┘
```

**Data processing pipeline:**

```
Raw 16-bit frame (hundredths of Kelvin)
    │
    ▼
raw_to_celsius(): (raw / 100.0) - 273.15 → float32 Celsius map
    │
    ▼
colorize_celsius(): np.clip + cv2.applyColorMap(INFERNO) → BGR8 image
    │
    ▼
overlay_box(): temperature text label at center pixel
    │
    ▼
cv2.resize(): scale up by view_scale (e.g. 3×)
    │
    ▼
MJPEG delivery to browser
```

---

## Module-by-Module Breakdown

### `geovision/` — GeoVision Camera Package

The core package for all GeoVision camera interactions.

| File | Class / Function | Purpose |
|---|---|---|
| [`config.py`](../geovision/config.py) | `CameraCredentials` | Frozen dataclass holding IP, username, password. Builds RTSP and HTTP URLs. |
| | `StreamProfile` | Frozen dataclass: `profile_id`, `channel`, `expected_fps`. |
| | `DEFAULT_CREDENTIALS` | Singleton built from `GEOVISION_IP/USER/PASS` env vars. |
| | `RGB_STREAM`, `RGB_PREVIEW_STREAM`, `THERMAL_STREAM` | Pre-configured `StreamProfile` instances. |
| | `configure_opencv_transport()` | Sets `OPENCV_FFMPEG_CAPTURE_OPTIONS` to force TCP transport. |
| [`streams.py`](../geovision/streams.py) | `RTSPStream` | Threaded RTSP capture → latest-frame buffer → MJPEG generator. Auto-reconnect on failure. JPEG cache for multi-client efficiency. |
| [`temperature.py`](../geovision/temperature.py) | `TemperatureClient` | HTTP client for `GetDotTemperature` and `GetTemperatureCurrentInfo` API. XML request/response parsing. Configurable conversion factor and offset. |
| [`overlay.py`](../geovision/overlay.py) | `draw_crosshair()`, `draw_label()` | OpenCV drawing helpers for the standalone thermal viewer (`temp_test.py`). |
| [`aruco_stream.py`](../geovision/aruco_stream.py) | `ArucoStream` | Extends `RTSPStream`. Runs ArUco detection on a subsampled frame every N frames. Annotates in-place with bounding boxes, corner dots, ID labels, and per-marker motion trails (color-coded, fading thickness). |
| [`barcode_stream.py`](../geovision/barcode_stream.py) | `BarcodeStream` | Reads frames from an existing `RTSPStream` (the RGB source). Feeds them through a `YoloBarcodeEngine` for detection and annotation. Periodic garbage collection and optional CUDA cache flushing. |

---

### `rgm/` — RGM USB Thermal Sensor Package

| File | Class / Function | Purpose |
|---|---|---|
| [`io.py`](../rgm/io.py) | `open_camera()` | Opens the USB camera with DirectShow or MSMF backend. Disables RGB conversion, requests Y16 pixel format for raw 16-bit thermal data. |
| | `coerce_to_u16_2d()` | Normalizes various frame layouts (8-bit, 16-bit, 3-channel, planar) into a consistent 2D uint16 array. |
| [`processing.py`](../rgm/processing.py) | `raw_to_celsius()` | Converts raw sensor units (hundredths of Kelvin) to Celsius: `(raw / 100) - 273.15`. |
| | `colorize_celsius()` | Maps a Celsius float32 array to a BGR image using the Inferno colormap. |
| | `overlay_box()` | Draws a semi-transparent text label box on the frame. |
| [`streaming.py`](../rgm/streaming.py) | `RGMThermalStream` | Full threaded pipeline: USB capture → coerce → Celsius → colorize → scale → MJPEG. Provides `latest_center()` for the center-pixel temperature readout. |

---

### `yolo_barcode_package/` — YOLO Barcode Detection

A self-contained package for barcode detection and decoding using YOLOv8.

| File | Class / Function | Purpose |
|---|---|---|
| [`config.py`](../yolo_barcode_package/config.py) | `PipelineConfig` | All model/inference settings (model path, device, confidence, image size, decode options, save flags). |
| | `StreamConfig` | Cadence settings for streaming mode (detect every N frames, cache TTL, IoU threshold). |
| | `LiveConfig` | Settings for the RTSP live session runner (display, recording, session logging). |
| [`core.py`](../yolo_barcode_package/core.py) | `BarcodeCorePipeline` | The heavy lifter: loads YOLOv8 model, runs detection, crops barcode regions, and decodes using a **multi-library multi-variant strategy**: |
| | | 1. Detect barcode regions with YOLO |
| | | 2. Pad and crop each region |
| | | 3. Optionally refine ROI via gradient-based contour analysis |
| | | 4. Generate preprocessing variants (original, CLAHE, sharpened, Otsu, 2× upscaled, rotated) |
| | | 5. Try decoding each variant with **zxing-cpp** first, then **pyzbar** as fallback |
| | | 6. Score candidates (prefer Code128 format, 2-digit numeric IDs) |
| | | 7. If primary decode fails, retry with wider crop padding |
| [`engine.py`](../yolo_barcode_package/engine.py) | `YoloBarcodeEngine` | Unified API wrapping `BarcodeCorePipeline` + `BarcodeStreamEngine`. Provides `process_frame()`, `process_image_path()`, `process_stream_frame()`, and `process_rtsp()`. |
| [`stream.py`](../yolo_barcode_package/stream.py) | `BarcodeStreamEngine` | Cadence-aware wrapper: runs full YOLO detection every N frames, reuses cached bounding boxes on intermediate frames. |
| [`live.py`](../yolo_barcode_package/live.py) | `run_live_rtsp_session()` | Complete RTSP session runner with: threaded frame grabber, YOLO processing loop, session logging (detection intervals with timestamps), optional annotated video recording, and JSON session export. |
| | `_SessionLogger` | Tracks barcode detection intervals (start/end frame, duration, max confidence) and exports a session summary JSON. |
| [`runner.py`](../yolo_barcode_package/runner.py) | `run_images()` | Batch-processes a folder of images, saves annotated outputs and detection metadata. |
| | `run_from_settings()`, `run_live_from_settings()` | Convenience runners that read from `settings.py`. |
| [`settings.py`](../yolo_barcode_package/settings.py) | `PIPELINE`, `STREAM`, `LIVE` | Editable preset configurations for quick testing without environment variables. |
| [`weights/`](../yolo_barcode_package/weights/) | `YOLOV8s_Barcode_Detection.pt` | Pre-trained YOLOv8s model (~22 MB) fine-tuned for barcode region detection. |

---

### Root Application Files

| File | Purpose |
|---|---|
| [`app.py`](../app.py) | Flask application factory. Creates all streams (RGB, thermal, RGM, ArUco, barcode), wires up routes, manages the settings form, and handles graceful shutdown. Runs on port 8000. |
| [`barcode_service.py`](../barcode_service.py) | Separate Flask process for barcode detection. Connects its own RTSP stream to the full-res RGB profile, runs YOLO inference independently. Exposes `/video/barcode`, `/barcode/detections`, and `/configure/geovision` endpoints on port 8100. |
| [`templates/index.html`](../templates/index.html) | Jinja2 HTML template for the web dashboard. Conditionally renders each stream pane based on availability flags. |
| [`static/css/style.css`](../static/css/style.css) | Dark-themed UI styling with thermal crosshair overlay animations, detection badges, and responsive layout. |
| [`static/js/main.js`](../static/js/main.js) | Frontend JavaScript: click-to-measure temperature coordinates, overlay positioning, RGM/ArUco/barcode badge polling, GeoVision settings form AJAX submission, stream reconnection logic. |

---

### Data Flow Summary

```
GeoVision Camera ─── RTSP (profile2) ──► RTSPStream (RGB preview)
                                             │
                 ─── RTSP (profile4) ──► RTSPStream (Thermal)
                                             │
                 ─── HTTP :80 ────────► TemperatureClient
                                             │
                 ─── RTSP (profile1) ──► RTSPStream (Barcode svc)
                                             │
                                             ▼
RGM Sensor ──── USB / DirectShow ──────► RGMThermalStream

All streams ──► MJPEG generator ──► Flask routes ──► Browser
```

---

## Threading Model

The toolkit spawns multiple daemon threads:

| Thread | Started by | Responsibility |
|---|---|---|
| `RTSPStream-RGB` | `app.py` | Continuously reads from RGB preview RTSP stream |
| `RTSPStream-Thermal` | `app.py` | Continuously reads from thermal RTSP stream |
| `RTSPStream-ArUco` | `app.py` | Reads + detects ArUco markers (if enabled) |
| `BarcodeStream-Barcode` | `app.py` (in-process) or `barcode_service.py` | Polls RGB frames, runs YOLO inference |
| `RGMStream` | `app.py` | Reads USB thermal sensor frames |
| Main thread | `app.py` | Flask HTTP request handling (MJPEG generators, API endpoints) |

All threads are daemon threads — they terminate when the main process exits. A `config_lock` serializes credential updates to prevent race conditions during stream restarts.

---

## Next Steps

→ [API Reference](api-reference.md) — endpoint details with request/response examples  
→ [Configuration Reference](configuration.md) — all environment variables
