# Quick Start

Get the dashboard running in under two minutes.

---

## 1. Set Camera Credentials

Set the environment variables for your GeoVision camera (or skip this and configure in the web UI later):

```powershell
$env:GEOVISION_IP = "192.168.0.10"
$env:GEOVISION_USER = "admin"
$env:GEOVISION_PASS = "admin123"
```

> **Linux / macOS:**
> ```bash
> export GEOVISION_IP="192.168.0.10"
> export GEOVISION_USER="admin"
> export GEOVISION_PASS="admin123"
> ```

If you don't set these, the app uses the defaults shown above.

---

## 2. Start the Application

```powershell
python app.py
```

You'll see output like:

```
[Barcode] Started separate service on port 8100
[RGM] Thermal camera initialized        # (only if RGM USB sensor is plugged in)
[ArUco] Disabled (ENABLE_ARUCO=false)    # ArUco is off by default
 * Running on http://0.0.0.0:8000
```

---

## 3. Open the Dashboard

Navigate to:

```
http://localhost:8000
```

You'll see the multi-stream viewer with up to five panes:

| Pane | What it shows |
|---|---|
| **GeoVision RGB** | Live RGB camera feed (preview resolution) |
| **GeoVision Thermal** | Live thermal feed — click anywhere to measure temperature |
| **RGM Thermal** | Local USB thermal sensor with center-point readout |
| **ArUco Tracking** | RGB feed with ArUco marker detection overlay |
| **Barcode Tracking** | RGB feed with YOLO barcode detection + decode |

---

## 4. Change Settings at Runtime

Use the **GeoVision Camera Settings** panel at the top of the page to update the camera IP, username, or password without restarting the app. Click **Apply & Restart Streams** and all video panes will reconnect with the new credentials.

---

## Common Startup Variations

### Disable thermal (RGB-only mode)

```powershell
$env:ENABLE_THERMAL = "false"
python app.py
```

### Disable the RGM sensor

```powershell
$env:ENABLE_RGM = "false"
python app.py
```

### Enable ArUco detection

```powershell
$env:ENABLE_ARUCO = "true"
python app.py
```

### Disable barcode detection

```powershell
$env:ENABLE_BARCODE = "false"
python app.py
```

### Debug mode

```powershell
$env:FLASK_DEBUG = "true"
python app.py
```

---

## Verify Camera Connection First

If you're not sure the camera is reachable, run the simple RGB viewer:

```powershell
python demo.py
```

A window will pop up showing the live RGB feed. Press `q` to quit. If this works, the full dashboard will work too.

---

## Next Steps

→ [Web UI Guide](web-ui-guide.md) — detailed walkthrough of each UI pane  
→ [Configuration Reference](configuration.md) — full list of environment variables  
→ [Helper Scripts](helper-scripts.md) — standalone tools for testing and recording
