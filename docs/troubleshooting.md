# Troubleshooting

Common issues and their solutions.

---

## Camera Connection Issues

### "Stream shows nothing / black frame"

**Symptoms:** The web UI shows a blank or black image for RGB or thermal.

**Possible causes and fixes:**

| Cause | Fix |
|---|---|
| Wrong IP address | Verify with `ping 192.168.0.10`. Update `GEOVISION_IP` or the web UI settings form. |
| Wrong credentials | Double-check username/password. Try logging into the camera's web admin at `http://<camera-ip>`. |
| Wrong RTSP profile | Verify the profile exists on the camera. Test with VLC: `rtsp://admin:pass@ip:554/profile2`. |
| Firewall blocking port 554 | Ensure RTSP port 554 (TCP) is not blocked between your PC and the camera. |
| Camera not on same subnet | If camera is `192.168.0.10` and your PC is `192.168.1.x`, they can't communicate. Adjust network settings. |

**Quick test:**

```powershell
python demo.py
```

If this shows a live feed, the RTSP connection is fine and the issue is elsewhere.

---

### "Failed to connect with provided settings"

**Symptoms:** After clicking "Apply & Restart Streams" in the web UI, you get an error.

**Fix:** The toolkit tried to open a new RTSP connection with the provided credentials and failed. Verify:
1. The camera is reachable (ping it)
2. The credentials are correct (log into camera admin panel)
3. RTSP is enabled on the camera

---

## Temperature Issues

### "Failed to get temperature" / Temperature returns `None`

**Possible causes:**

| Cause | Fix |
|---|---|
| Temperature API not enabled | Log into camera admin → Settings → Thermal → Enable temperature measurement. See [Camera Setup](camera-setup.md#8-temperature-api-setup). |
| Thermal channel not on channel 2 | The toolkit sends temperature queries to `/GetDotTemperature/2`. If your camera maps thermal to a different channel, update the channel number in code. |
| Camera doesn't support temperature API | Not all GeoVision cameras have thermal sensors that support per-pixel temperature queries. Check your model's specifications. |
| Network timeout | The default timeout is 3 seconds. If the camera is under heavy load, it may not respond in time. |

**Debug with verbose logging:**

```powershell
$env:TEMPERATURE_DEBUG = "true"
python app.py
```

This prints the full XML request and response for every temperature query.

**CLI test:**

```powershell
python temperature_api_test.py
```

---

### "Temperature values seem wrong"

The raw temperature value from the camera is divided by 100 (hundredths of °C). If your readings seem off by a factor of 10 or 100:

1. Enable debug logging (`TEMPERATURE_DEBUG=true`)
2. Check the raw value printed: e.g. `raw=2835`
3. At `/100` that's `28.35°C` — does that match the physical temperature?
4. If the camera uses tenths (not hundredths), you'll need to adjust `temp_conversion_factor` in `TemperatureClient`

---

### "Crosshair appears in the wrong position"

The click-to-measure coordinate system maps browser click pixels to thermal frame pixels. Issues can arise from:

| Symptom | Fix |
|---|---|
| Crosshair at the opposite X side | Toggle `flipXCoordinates = true` in `static/js/main.js`. Some cameras use (0,0) at top-right. |
| Crosshair off by a few pixels | Normal — the browser may round differently than the camera. Small offsets are expected. |
| Camera returns different coordinates | The camera may "snap" coordinates to valid positions. The `coordinates_match` field in the API response indicates this. |

---

## RGM USB Thermal Sensor Issues

### "RGM camera not available"

**Possible causes:**

| Cause | Fix |
|---|---|
| USB sensor not plugged in | Connect the RGM thermal sensor via USB. |
| Wrong device index | If you have multiple cameras, try `RGM_DEVICE_INDEX=1` or `2`. |
| Wrong capture backend | Try toggling `RGM_USE_MSMF`. DirectShow (`false`) works better on most Windows setups, but some devices need MSMF (`true`). |
| Driver not installed | Ensure the device drivers are installed and the camera appears in Windows Device Manager. |
| Another application using the camera | Only one application can access a USB camera at a time. Close any other camera apps (including Windows Camera). |

**Disable if not needed:**

```powershell
$env:ENABLE_RGM = "false"
python app.py
```

---

### "Frame captured but not 16-bit"

This message appears when the RGM module receives frames but they're not in the expected 16-bit raw format. This usually means:

- The camera is outputting standard 8-bit RGB instead of raw thermal data
- The `CAP_PROP_FOURCC` setting for Y16 format wasn't accepted by the driver

The toolkit will still display the frames using a fallback grayscale conversion, but temperature readings won't be accurate.

---

## Barcode Detection Issues

### "Barcode service unavailable" / Barcode stream blank

**If using service mode (`BARCODE_USE_SERVICE=true`):**

| Cause | Fix |
|---|---|
| Service hasn't started yet | Wait a few seconds — the YOLO model takes time to load. The browser will auto-retry. |
| Service crashed | Check the terminal output for `[BarcodeService]` error messages. |
| Port conflict | Another process may be using port 8100. Change with `BARCODE_SERVICE_PORT`. |
| Model weights missing | Verify `yolo_barcode_package/weights/YOLOV8s_Barcode_Detection.pt` exists (~22 MB). |

**If using in-process mode (`BARCODE_USE_SERVICE=false`):**

| Cause | Fix |
|---|---|
| CUDA out of memory | Try `BARCODE_DEVICE=cpu` or reduce `BARCODE_IMGSZ` to 640. |
| Import error for torch/ultralytics | Reinstall: `pip install ultralytics torch`. |

### "Barcode detected but not decoded"

If you see orange bounding boxes (detected regions) without text labels:

- Decoding is **disabled by default** (`BARCODE_ENABLE_DECODE=false`). Set to `true` if you need it.
- Even with decoding enabled, some barcodes may not decode if they're blurry, too small, or at a steep angle.
- Try increasing `BARCODE_IMGSZ` (e.g. 1280) for more resolution.
- Try lowering `BARCODE_CONF` (e.g. 0.25) for more detections (with more false positives).

---

## ArUco Detection Issues

### "ArUco pipeline disabled"

ArUco is **disabled by default**. Enable with:

```powershell
$env:ENABLE_ARUCO = "true"
python app.py
```

### "No markers detected"

- Ensure you're using **4×4 ArUco markers** (dict_id = `DICT_4X4_50`). Other dictionary types won't be detected.
- Markers must be printed clearly and be at least ~2% of the frame width to be detected (controlled by `minMarkerPerimeterRate`).
- Detection runs every 3 frames on a 75% resolution image. Very fast motion may cause missed detections.

---

## General Issues

### "Flask debug mode warning"

```
WARNING: This is a development server. Do not use it in production.
```

This is expected — the toolkit uses Flask's built-in server for simplicity. For production deployments, consider using Gunicorn or Waitress behind a reverse proxy.

### "Port 8000 already in use"

Another process is using port 8000. Either:
- Stop the other process
- Run on a different port: modify the `port=8000` line in `app.py`

### Keyboard interrupt during shutdown

The application registers `atexit` handlers to stop all streams gracefully. If you see thread-related warnings on `Ctrl+C`, they're harmless — all threads are daemon threads and will terminate with the main process.

---

## Getting Help

If your issue isn't listed here:

1. Enable debug logging:
   ```powershell
   $env:TEMPERATURE_DEBUG = "true"
   $env:FLASK_DEBUG = "true"
   ```
2. Check terminal output for `[bracketed]` log messages
3. Test individual components with the [helper scripts](helper-scripts.md)
4. Open an issue on the GitHub repository with your terminal output

---

## Next Steps

→ [Camera Setup](camera-setup.md) — verify hardware configuration  
→ [Configuration Reference](configuration.md) — check environment variable settings
