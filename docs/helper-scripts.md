# Helper Scripts

The repository includes several standalone Python scripts for testing, debugging, and recording — independent of the main Flask dashboard.

---

## `demo.py` — Simple RGB Stream Viewer

The quickest way to verify your GeoVision camera is reachable and streaming.

**What it does:**
- Opens an RTSP connection to the full-resolution RGB stream (`profile1`)
- Displays the live feed in an OpenCV window
- Press `q` to quit

**Usage:**

```powershell
python demo.py
```

**When to use it:**
- First-time setup — verify the camera is reachable before running the full dashboard
- Debugging — isolate RTSP connectivity issues from Flask / browser complications
- Quick preview — check what the camera sees without starting the full app

**Configuration:**
Uses `DEFAULT_CREDENTIALS` and `RGB_STREAM` from `geovision/config.py`, which read from `GEOVISION_IP`, `GEOVISION_USER`, and `GEOVISION_PASS` environment variables.

---

## `temp_test.py` — Interactive Thermal Viewer

A standalone thermal camera viewer with **click-to-measure** temperature functionality — no browser required.

**What it does:**
- Opens an RTSP connection to the thermal stream (`profile4`)
- Displays the thermal feed in an OpenCV window
- **Click anywhere** on the image to query the temperature at that pixel
- A green crosshair and temperature label appear at the clicked location
- Temperature refreshes in a background thread every 0.5 seconds
- Press `q` to quit

**Usage:**

```powershell
python temp_test.py
```

**When to use it:**
- Test the temperature API without the web UI
- Debug coordinate mapping and temperature conversion
- Verify the thermal channel is working correctly

**How it works internally:**
1. `SharedState` holds the current target coordinates and temperature
2. An OpenCV mouse callback captures click events and updates the target
3. A background `temperature_worker` thread polls `TemperatureClient.get_dot_temperature()` whenever the target changes
4. The main loop draws a crosshair and label overlay on each frame using `draw_crosshair()` and `draw_label()` from `geovision.overlay`

---

## `record_test.py` — Dual-Stream Recorder

Records both RGB and thermal streams simultaneously to AVI files.

**What it does:**
- Opens RTSP connections to both RGB (`profile1`) and thermal (`profile4`) streams
- Displays both in separate OpenCV windows
- Press `r` to **start/stop recording** — a red dot indicator appears while recording
- Press `q` to quit
- Recordings are saved as timestamped AVI files: `rgb_YYYYMMDD_HHMMSS.avi` and `thermal_YYYYMMDD_HHMMSS.avi`

**Usage:**

```powershell
python record_test.py
```

**Controls:**

| Key | Action |
|---|---|
| `r` | Toggle recording on/off |
| `q` | Quit |

**Output files:**

```
rgb_20251112_232519.avi        # XVID-encoded RGB recording
thermal_20251112_232519.avi    # XVID-encoded thermal recording
```

**When to use it:**
- Capture camera footage for offline analysis
- Document camera positioning and field of view
- Record thermal events for later review

**Notes:**
- Uses XVID codec (`cv2.VideoWriter_fourcc(*"XVID")`)
- RGB records at the profile's configured FPS (default 30)
- Thermal records at the thermal profile's FPS (default 15)
- Existing recordings are stored in the `records/` directory

---

## `temperature_api_test.py` — CLI Temperature API Probe

A minimal CLI tool to test the GeoVision temperature API endpoints directly.

**What it does:**
1. Queries **ROI temperature statistics** (`GetTemperatureCurrentInfo`) — returns min/max/avg temperatures for configured regions
2. Queries a **dot temperature** (`GetDotTemperature`) at pixel (192, 144)
3. Prints the results

**Usage:**

```powershell
python temperature_api_test.py
```

**Example output:**

```
--- 1. ROI Statistics ---
ROI stats: {'max': 32.5, 'min': 22.1, 'avg': 27.3}

--- 2. Dot Temperature ---
Requested (192, 144) -> Camera reported (192, 144) = 28.35 °C
```

**When to use it:**
- Verify the temperature HTTP API is enabled on the camera
- Check if ROI regions are configured
- Debug temperature conversion (raw hundredths → °C)
- Quick sanity check before relying on the web UI's temperature overlay

---

## Summary

| Script | Purpose | Key feature |
|---|---|---|
| `demo.py` | RGB-only viewer | Fastest connectivity check |
| `temp_test.py` | Thermal viewer | Click-to-measure temperature |
| `record_test.py` | Dual-stream recorder | Press `r` to record AVI |
| `temperature_api_test.py` | CLI API probe | Test temperature endpoints |

---

## Next Steps

→ [Web UI Guide](web-ui-guide.md) — the browser-based dashboard  
→ [Troubleshooting](troubleshooting.md) — common issues and fixes
