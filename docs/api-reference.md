# API Reference

All endpoints are served by the main Flask application on port **8000** (default).

---

## Health Check

### `GET /healthz`

Returns a simple health check response.

**Response:**
```json
{"status": "ok"}
```

---

## Video Streams

All video endpoints return **MJPEG** streams (`Content-Type: multipart/x-mixed-replace; boundary=frame`). Point an `<img>` tag or a video player at these URLs.

### `GET /video/rgb`

Live RGB camera feed (preview resolution).

**Query parameters:** None

**Response:** MJPEG stream (JPEG quality controlled by `RGB_JPEG_QUALITY`, max width by `RGB_PREVIEW_MAX_WIDTH`)

**Example:**
```html
<img src="http://localhost:8000/video/rgb" alt="RGB Stream" />
```

---

### `GET /video/thermal`

Live thermal camera feed.

**Query parameters:** None

**Response:** MJPEG stream (JPEG quality 80, frame rate throttled at thermal FPS)

**Returns 404** if `ENABLE_THERMAL=false`.

---

### `GET /video/rgm`

Local RGM USB thermal camera feed (colorized Inferno palette).

**Response:** MJPEG stream (JPEG quality 75, frame rate ~15 fps)

**Returns 503** if the RGM camera is not available or `ENABLE_RGM=false`.

---

### `GET /video/aruco`

RGB stream annotated with ArUco marker detections and motion trails.

**Response:** MJPEG stream (JPEG quality 70)

**Returns 503** if ArUco is disabled (`ENABLE_ARUCO=false`).

---

### `GET /video/barcode`

RGB stream annotated with YOLO barcode detections and decoded text.

In **service mode** (`BARCODE_USE_SERVICE=true`), this proxies the stream from the barcode subprocess on port 8100.

**Response:** MJPEG stream (JPEG quality 70)

**Returns 503** if the barcode pipeline is disabled or the service is unavailable.

---

## Temperature

### `GET /temperature`

Query the GeoVision camera's temperature at a specific pixel coordinate on the thermal image.

**Query parameters:**

| Param | Type | Required | Description |
|---|---|---|---|
| `x` | int | ✅ | X pixel coordinate (0-based, from left) |
| `y` | int | ✅ | Y pixel coordinate (0-based, from top) |

**Success response (200):**

```json
{
  "temperature": 28.35,
  "x": 192,
  "y": 144,
  "requested_x": 192,
  "requested_y": 144,
  "coordinates_match": true
}
```

| Field | Description |
|---|---|
| `temperature` | Temperature in °C (rounded to 2 decimal places) |
| `x`, `y` | Coordinates confirmed by the camera |
| `requested_x`, `requested_y` | Original coordinates sent in the request |
| `coordinates_match` | `true` if camera confirmed the same coordinates; `false` if it snapped to different ones |

**Error responses:**

| Status | Condition |
|---|---|
| 400 | Missing `x` or `y`, or negative coordinates |
| 500 | Camera returned an error or unparseable response |
| 503 | Thermal stream disabled |

**Example:**

```bash
curl "http://localhost:8000/temperature?x=192&y=144"
```

---

### `GET /rgm/center_temperature`

Returns the current center-pixel temperature reading from the RGM USB thermal sensor.

**Response (200):**

```json
{
  "raw": 30015.0,
  "temp_c": 26.85,
  "temp_f": 80.33
}
```

| Field | Description |
|---|---|
| `raw` | Raw sensor value (hundredths of Kelvin) |
| `temp_c` | Temperature in Celsius |
| `temp_f` | Temperature in Fahrenheit |

**Returns 503** if the RGM camera is not available.

---

## Detection Results

### `GET /aruco/detections`

Returns the latest ArUco marker detection results.

**Response (200):**

```json
{
  "ids": [3, 7, 12],
  "count": 3,
  "timestamp": 1735000000.123
}
```

| Field | Description |
|---|---|
| `ids` | List of currently detected marker IDs |
| `count` | Number of detected markers |
| `timestamp` | Unix timestamp of the last detection run |

**Returns 503** (with `"disabled": true`) if ArUco is disabled.

---

### `GET /barcode/detections`

Returns the latest barcode detection results.

In **service mode**, this proxies from the barcode service on port 8100.

**Response (200):**

```json
{
  "ids": ["07", "12"],
  "count": 3,
  "decoded_count": 2,
  "timestamp": 1735000000.456,
  "device": "cuda:0"
}
```

| Field | Description |
|---|---|
| `ids` | List of unique decoded barcode IDs (sorted strings) |
| `count` | Total number of detected barcode regions (including un-decoded) |
| `decoded_count` | Number of successfully decoded barcodes |
| `timestamp` | Unix timestamp of the last detection run |
| `device` | Inference device used (e.g. `cuda:0`, `cpu`) |

**Returns 503** (with `"disabled": true`) if the barcode pipeline is disabled.

---

## Configuration

### `POST /configure/geovision`

Update camera credentials at runtime and restart all affected streams.

**Request body** (JSON or form-encoded):

```json
{
  "ip": "192.168.0.50",
  "username": "admin",
  "password": "newsecretpass"
}
```

| Field | Required | Description |
|---|---|---|
| `ip` | ✅ | New camera IP address |
| `username` | ✅ | New camera username |
| `password` | optional | New camera password (empty string if unchanged) |

**Success response (200):**

```json
{
  "status": "ok",
  "message": "GeoVision credentials updated"
}
```

**What happens behind the scenes:**

1. New `CameraCredentials` are created
2. New RTSP streams are opened with the new credentials
3. ArUco stream is restarted (if enabled)
4. Barcode service is notified of the credential change (if in service mode)
5. Old streams are gracefully stopped
6. All browser-connected MJPEG streams automatically get the new feed

**Error responses:**

| Status | Condition |
|---|---|
| 400 | Missing IP or username |
| 500 | Failed to connect with provided settings |

**Example:**

```bash
curl -X POST http://localhost:8000/configure/geovision \
  -H "Content-Type: application/json" \
  -d '{"ip":"192.168.0.50","username":"admin","password":"newpass"}'
```

---

## Barcode Service Endpoints (Port 8100)

When `BARCODE_USE_SERVICE=true`, a separate Flask process runs on port 8100 with its own endpoints:

| Endpoint | Mirrors |
|---|---|
| `GET /healthz` | Health check (includes `device` field) |
| `GET /video/barcode` | MJPEG barcode-annotated stream |
| `GET /barcode/detections` | Latest detection JSON |
| `POST /configure/geovision` | Credential update (called automatically by main app) |

These are not intended to be accessed directly by end users — the main app on port 8000 proxies them.

---

## Next Steps

→ [Helper Scripts](helper-scripts.md) — standalone tools  
→ [Troubleshooting](troubleshooting.md) — common issues
