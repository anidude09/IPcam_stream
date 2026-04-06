# Web UI Guide

The browser dashboard at `http://localhost:8000` displays up to five live video panes plus a settings panel. Each is detailed below.

---

## Settings Panel

At the top of the page, the **GeoVision Camera Settings** panel lets you change camera credentials at runtime without restarting the application.

| Field | Purpose |
|---|---|
| **Camera IP** | The GeoVision camera's IP address on your network |
| **Username** | Camera admin username |
| **Password** | Camera admin password |

Click **Apply & Restart Streams** to apply. The status indicator shows:
- **Idle** — no changes pending
- **Applying...** — reconnecting to camera
- **Streams restarting with new settings** — success
- **Error message** — connection failed (check IP / credentials)

All video panes (RGB, thermal, ArUco, barcode) automatically reconnect with the new credentials. The barcode service process (if running separately) is also notified.

---

## GeoVision RGB Pane

Displays the live RGB camera feed from the preview profile (`profile2` by default).

- **Resolution:** Controlled by the camera's profile2 settings (typically 640×480 or 1280×720)
- **Max width:** Capped by `RGB_PREVIEW_MAX_WIDTH` (default 1280px) for bandwidth efficiency
- **JPEG quality:** Controlled by `RGB_JPEG_QUALITY` (default 75)
- **Low-latency mode:** When `RGB_LOW_LATENCY=true` (default), frames are pushed as fast as they arrive with no throttling

This pane is always visible.

---

## GeoVision Thermal Pane

Displays the live thermal feed with **interactive temperature measurement**.

### Click-to-Measure

1. **Click anywhere** on the thermal image
2. A green **crosshair** appears at the clicked location
3. The toolkit queries the camera's `GetDotTemperature` HTTP API at that pixel coordinate
4. The temperature is displayed in a floating label: e.g. `28.35 °C`
5. The reading **auto-refreshes every 1 second** at the same coordinates

### How It Works Under the Hood

```
Browser click → calculate (x, y) in frame pixels
             → GET /temperature?x=192&y=144
             → Flask calls TemperatureClient.get_dot_temperature()
             → POST http://<camera>/GetDotTemperature/2 (XML body)
             → Camera returns raw temp (hundredths of °C)
             → Displayed as overlay on the stream
```

### Coordinate System

The JavaScript calculates click coordinates relative to the actual thermal frame resolution (e.g. 384×288), not the displayed size. The conversion accounts for CSS scaling.

> **Coordinate flip:** If you notice the crosshair appearing on the wrong side, the `flipXCoordinates` flag in `main.js` can be toggled to account for cameras where (0,0) is at the top-right instead of top-left.

### Disabled State

If `ENABLE_THERMAL=false`, this pane shows a "Thermal stream disabled" placeholder.

---

## RGM Thermal Pane

Displays the feed from a **local USB thermal sensor** (RGM module).

- The raw 16-bit thermal data is converted to Celsius and colorized with the **Inferno** colormap
- A white dot marks the **center pixel**
- A floating badge shows the center-point temperature in both °C and °F
- The badge auto-updates every 1 second via polling `/rgm/center_temperature`

### Temperature Scale

The colormap range is configured via:
- `RGM_TEMP_MIN_C` (default `20`) — maps to the cold end of the Inferno palette
- `RGM_TEMP_MAX_C` (default `40`) — maps to the hot end

Objects outside this range will appear fully black or fully white.

### Scaling

The view scale multiplier (`RGM_VIEW_SCALE`, default `3`) upscales the small native resolution (e.g. 80×60 → 240×180) for easier viewing.

### Disabled State

If no USB thermal camera is detected, or `ENABLE_RGM=false`, this pane shows "RGM camera unavailable".

---

## ArUco Tracking Pane

Displays the RGB preview stream with real-time **ArUco fiducial marker detection**.

### What It Shows

- **Green bounding boxes** around detected ArUco markers
- **Yellow corner dots** at each marker's four corners
- **ID labels** (e.g. "ID: 7") above each marker
- **Motion trails** — colored polylines showing each marker's movement path over time (up to 120 frames of history)
- **Scanning indicator** — when no markers are detected, a "Scanning for ArUco tags..." label appears

### Detection Badge

A teal overlay badge in the top-left shows:
- `Scanning...` — no markers currently visible
- `Detected: #3, #7, #12` — lists currently visible marker IDs

The badge polls `/aruco/detections` every 1 second.

### Configuration

- ArUco is **disabled by default** — set `ENABLE_ARUCO=true` to enable
- Uses the **4×4 (50 markers)** ArUco dictionary by default
- Detection runs every 3 frames (configurable) to reduce CPU load
- Detection is performed at 75% resolution for speed, then coordinates are scaled back up

---

## Barcode Tracking Pane

Displays the RGB stream with **YOLO-based barcode detection and optional decoding**.

### What It Shows

- **Green bounding boxes** around detected barcodes
- **Decoded text labels** — if decoding is enabled, shows the extracted barcode ID (e.g. "07 (0.92)")
- **Orange boxes** — for detected-but-not-decoded barcodes

### Detection Badge

A teal overlay badge shows:
- `Scanning... [cuda:0]` — no barcodes detected, shows inference device
- `Detected: #07, #12 [cuda:0]` — lists decoded barcode IDs

### Architecture Options

The barcode detection can run in two modes:

| Mode | Env variables | How it works |
|---|---|---|
| **Service mode** (default) | `BARCODE_USE_SERVICE=true` | A separate Flask process (`barcode_service.py`) runs YOLO inference on port 8100. The main app proxies the MJPEG stream. Isolates GPU memory from the main process. |
| **In-process mode** | `BARCODE_USE_SERVICE=false` | YOLO runs directly in the main Flask process. Simpler but uses more memory. |

### Disabled State

If `ENABLE_BARCODE=false`, this pane shows "Barcode pipeline disabled".

---

## Browser Compatibility

The dashboard uses standard MJPEG streaming (`multipart/x-mixed-replace`), which is supported natively by:

| Browser | Supported |
|---|---|
| Chrome / Chromium | ✅ |
| Firefox | ✅ |
| Safari | ✅ |
| Edge | ✅ |

No browser extensions or plugins are required.

---

## Next Steps

→ [Configuration Reference](configuration.md) — tune every aspect of the streams  
→ [API Reference](api-reference.md) — programmatic access to all endpoints  
→ [Troubleshooting](troubleshooting.md) — fixing common issues
