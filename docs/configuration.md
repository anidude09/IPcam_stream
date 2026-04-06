# Configuration Reference

Every tunable parameter in the toolkit is set via **environment variables**. All have sensible defaults — you only need to set the ones you want to customize.

---

## Camera Credentials

| Variable | Default | Description |
|---|---|---|
| `GEOVISION_IP` | `192.168.0.10` | IP address of the GeoVision camera |
| `GEOVISION_USER` | `admin` | Camera admin username |
| `GEOVISION_PASS` | `admin123` | Camera admin password |

> These can also be changed at runtime via the web UI settings panel.

---

## RTSP Stream Profiles

| Variable | Default | Description |
|---|---|---|
| `GEOVISION_RGB_PROFILE` | `profile1` | Full-resolution RGB RTSP profile. Used by barcode detection for maximum decode accuracy. |
| `GEOVISION_RGB_PREVIEW_PROFILE` | `profile2` | Lower-resolution RGB RTSP profile. Used by the web UI preview and ArUco detection. |
| `GEOVISION_RGB_PREVIEW_FPS` | `30.0` | Expected frame rate of the preview profile. Used for MJPEG timing hints. |
| `GEOVISION_THERMAL_PROFILE` | `profile4` | Thermal RTSP profile. Must be mapped to the thermal channel (channel 2) in the camera admin. |

---

## Feature Toggles

| Variable | Default | Description |
|---|---|---|
| `ENABLE_THERMAL` | `true` | Enable the GeoVision thermal stream pane. Set to `false` for RGB-only operation. |
| `ENABLE_RGM` | `true` | Enable the local RGM USB thermal sensor pane. Automatically disabled if no USB thermal camera is found. |
| `ENABLE_ARUCO` | `false` | Enable the ArUco marker detection pipeline. Off by default to save CPU. |
| `ENABLE_BARCODE` | `true` | Enable the YOLO barcode detection pipeline. |

---

## RGB Stream Tuning

| Variable | Default | Description |
|---|---|---|
| `RGB_LOW_LATENCY` | `true` | When `true`, frames are pushed to the browser as fast as they arrive (no FPS throttling). When `false`, frames are paced at the profile's expected FPS. |
| `RGB_JPEG_QUALITY` | `75` | JPEG compression quality for the RGB MJPEG stream (1–100). Lower = smaller bandwidth, more artifacts. |
| `RGB_PREVIEW_MAX_WIDTH` | `1280` | Maximum pixel width for the RGB preview stream. Frames wider than this are downscaled server-side. |

---

## RGM Thermal Sensor

| Variable | Default | Description |
|---|---|---|
| `RGM_DEVICE_INDEX` | `0` | OpenCV camera index for the USB thermal sensor. Change if you have multiple cameras. |
| `RGM_USE_MSMF` | `false` | Use the Windows MSMF backend instead of DirectShow. Try toggling this if the camera doesn't open. |
| `RGM_VIEW_SCALE` | `3` | Integer scale factor applied to the tiny native thermal resolution (e.g. 80×60 × 3 = 240×180). |
| `RGM_TEMP_MIN_C` | `20.0` | Lower bound of the Inferno colormap (°C). Pixels at or below this temperature appear as the cold end of the palette. |
| `RGM_TEMP_MAX_C` | `40.0` | Upper bound of the Inferno colormap (°C). Pixels at or above this temperature appear as the hot end. |

---

## Barcode Detection

### Service Mode

| Variable | Default | Description |
|---|---|---|
| `BARCODE_USE_SERVICE` | `true` | Run barcode detection in a separate process (recommended). Isolates GPU memory and prevents the YOLO model from blocking the main Flask app. |
| `BARCODE_SERVICE_PORT` | `8100` | Port for the barcode detection subprocess. |
| `BARCODE_SERVICE_URL` | `http://127.0.0.1:<port>` | Full base URL for the barcode service. Auto-generated from port if not set. |
| `BARCODE_SERVICE_AUTOSTART` | `true` | Automatically launch the barcode service as a subprocess when the main app starts. Set to `false` if you manage the service manually. |

### Model & Inference

| Variable | Default | Description |
|---|---|---|
| `BARCODE_MODEL_PATH` | `yolo_barcode_package/weights/YOLOV8s_Barcode_Detection.pt` | Path to the YOLOv8 barcode detection model weights. |
| `BARCODE_DEVICE` | `auto` | Inference device. `auto` selects CUDA if available, then MPS (Apple Silicon), then CPU. Explicit options: `cuda:0`, `mps`, `cpu`. |
| `BARCODE_CONF` | `0.35` | Minimum confidence threshold for YOLO detections (0.0–1.0). |
| `BARCODE_IMGSZ` | `960` | Input image size for YOLO inference. Larger = more accurate but slower. |
| `BARCODE_ENABLE_DECODE` | `false` | Enable barcode decoding (text extraction) after detection. Adds CPU overhead per detected barcode. |

### Performance Tuning

| Variable | Default | Description |
|---|---|---|
| `BARCODE_DETECT_EVERY_N` | `10` | Run full YOLO inference once every N frames. Between detection frames, the last bounding boxes are reused as overlays. |
| `BARCODE_CACHE_TTL_SEC` | `2.0` | Time-to-live for cached detection results (seconds). |
| `BARCODE_HOUSEKEEPING_SEC` | `15.0` | Interval between memory housekeeping passes (garbage collection, JPEG cache pruning, optional CUDA cache release). |
| `BARCODE_RELEASE_CUDA_CACHE` | `false` | Call `torch.cuda.empty_cache()` during housekeeping. Only useful if you're running low on GPU memory. |

---

## Temperature API

| Variable | Default | Description |
|---|---|---|
| `TEMPERATURE_DEBUG` | `false` | Enable verbose logging for temperature API requests and XML parsing. Useful for debugging camera API issues. |

---

## Flask Server

| Variable | Default | Description |
|---|---|---|
| `FLASK_DEBUG` | `false` | Enable Flask debug mode. **Do not use in production.** |

---

## Setting Environment Variables

### PowerShell (current session)

```powershell
$env:GEOVISION_IP = "192.168.1.50"
$env:ENABLE_ARUCO = "true"
python app.py
```

### PowerShell (one-liner)

```powershell
$env:GEOVISION_IP="192.168.1.50"; $env:ENABLE_ARUCO="true"; python app.py
```

### `.env` File (manual sourcing)

Create a `.env` file (git-ignored by default):

```env
GEOVISION_IP=192.168.1.50
GEOVISION_USER=admin
GEOVISION_PASS=mysecretpass
ENABLE_ARUCO=true
ENABLE_BARCODE=true
```

Then source it before running:

```powershell
Get-Content .env | ForEach-Object {
    if ($_ -match '^([^=]+)=(.*)$') {
        [Environment]::SetEnvironmentVariable($matches[1], $matches[2], 'Process')
    }
}
python app.py
```

---

## Next Steps

→ [Architecture](architecture.md) — understand how the code is organized  
→ [API Reference](api-reference.md) — programmatic access to endpoints
