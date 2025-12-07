# IPcam_stream - Cattle Monitoring System

A Flask-based application for real-time cattle monitoring using thermal cameras and RFID identification. The system streams video from GeoVision IP cameras (RGB + thermal) and a local RGM thermal sensor, allowing interactive temperature measurement. When cattle are scanned with an RFID reader, the system automatically captures frames from all cameras along with temperature readings and logs everything to CSV.

## Features

- 📹 **Live Streaming** - View GeoVision RGB, thermal, and RGM camera feeds side-by-side
- 🌡️ **Temperature Measurement** - Click anywhere on thermal streams to get instant readings
- 📡 **RFID Capture** - Auto-capture frames + temperatures when cattle tags are scanned
- ➕ **Multi-Camera** - Add/remove GeoVision cameras dynamically via web UI
- 📊 **CSV Logging** - All captures logged with timestamps, EID, and file paths

---

## Setup & Installation

### Prerequisites
- Python 3.8+
- GeoVision IP camera(s) on the same network
- RGM thermal camera (USB)
- AWR300 RFID reader (USB) - optional

### Step 1: Clone & Setup Virtual Environment

```powershell
cd C:\Users\aniruddh\IPcam_stream
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

### Step 2: Install Dependencies

```powershell
pip install -r requirements.txt
```

### Step 3: Configure (Optional)

Set environment variables for default camera and RFID:

```powershell
# GeoVision camera (optional - can add via UI)
$env:GEOVISION_IP="192.168.1.100"
$env:GEOVISION_USER="admin"
$env:GEOVISION_PASS="your_password"
$env:GEOVISION_NAME="Main Camera"

# RFID reader (optional)
$env:RFID_PORT="COM3"
$env:RFID_GROUP="Session_2024_12_07"

# RGM camera (optional - defaults usually work)
$env:RGM_DEVICE_INDEX="0"
```

### Step 4: Run the Application

```powershell
python app.py
```

### Step 5: Open Browser

Navigate to: **http://localhost:8000**

---

## Usage

### Adding a Camera
1. Fill in the "Add GeoVision Camera" form (name, IP, username, password)
2. Click "Add Camera"
3. Camera streams appear automatically

### Measuring Temperature
1. Click anywhere on a thermal stream (GeoVision or RGM)
2. Temperature displays at clicked point
3. Reading auto-refreshes every second

### RFID Capture
1. Connect AWR300 to USB
2. Start listener via API or environment variable
3. Scan cattle tag → frames + temps auto-saved to `data/`

### Manual Capture (Testing)
```powershell
curl -X POST http://localhost:8000/api/rfid/capture -H "Content-Type: application/json" -d "{\"eid\": \"TEST123\", \"group\": \"TestSession\"}"
```

---

## Project Structure

```
IPcam_stream/
├── app.py                  # Flask application
├── geovision/              # GeoVision camera modules
│   ├── camera_manager.py   # Multi-camera management
│   ├── streams.py          # RTSP streaming
│   └── temperature.py      # Temperature API
├── rgm/                    # RGM thermal camera
│   ├── streaming.py        # MJPEG streaming
│   └── processing.py       # Thermal processing
├── rfid/                   # RFID capture system
│   ├── capture_manager.py  # Frame capture + CSV logging
│   └── listener.py         # AWR300 serial listener
├── data/                   # Auto-created
│   ├── captures/           # Saved frames (JPEG)
│   └── cattle_captures.csv # Capture log
├── static/                 # Frontend assets
├── templates/              # HTML templates
└── requirements.txt        # Python dependencies
```

---

## API Reference

### Camera Management
| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/cameras` | GET | List all cameras |
| `/api/cameras` | POST | Add camera |
| `/api/cameras/<id>` | DELETE | Remove camera |

### Video Streams
| Endpoint | Description |
|----------|-------------|
| `/video/<id>/rgb` | GeoVision RGB stream |
| `/video/<id>/thermal` | GeoVision thermal stream |
| `/video/rgm` | RGM thermal stream |

### Temperature
| Endpoint | Description |
|----------|-------------|
| `/api/cameras/<id>/temperature?x=X&y=Y` | Get temp at point |
| `/rgm/center_temperature` | RGM center temp |

### RFID
| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/rfid/capture` | POST | Manual capture |
| `/api/rfid/status` | GET | Listener status |
| `/api/rfid/start` | POST | Start listener |
| `/api/rfid/stop` | POST | Stop listener |
| `/api/rfid/ports` | GET | List COM ports |

---

## Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `GEOVISION_IP` | - | Camera IP address |
| `GEOVISION_USER` | `admin` | Camera username |
| `GEOVISION_PASS` | `admin123` | Camera password |
| `RGM_DEVICE_INDEX` | `0` | USB camera index |
| `RFID_PORT` | - | Serial port (e.g., `COM3`) |
| `RFID_GROUP` | `default` | Capture group name |

---

## Output Data

### CSV Format (`data/cattle_captures.csv`)

| Column | Example |
|--------|---------|
| `eid` | `982000123456789` |
| `timestamp` | `2024-12-07T14:30:45` |
| `group` | `Morning_Weigh` |
| `rgb_frame_path` | `data/captures/.../geovision_rgb.jpg` |
| `thermal_frame_path` | `data/captures/.../geovision_thermal.jpg` |
| `rgm_frame_path` | `data/captures/.../rgm_thermal.jpg` |
| `geovision_temp_c` | `38.50` |
| `rgm_temp_c` | `32.10` |

---

## Troubleshooting

| Issue | Solution |
|-------|----------|
| Camera won't connect | Check IP, credentials, and firewall |
| RGM not detected | Try `$env:RGM_DEVICE_INDEX="1"` |
| RFID not working | Check COM port in Device Manager |
| Temperature wrong | Coordinates use 0-10000 normalized scale |

---

## Architecture

```
┌──────────────┐     ┌──────────────┐     ┌──────────────┐
│  GeoVision   │     │     RGM      │     │   AWR300     │
│  IP Camera   │     │   Thermal    │     │    RFID      │
│  (Network)   │     │    (USB)     │     │   (Serial)   │
└──────┬───────┘     └──────┬───────┘     └──────┬───────┘
       │                    │                    │
       └────────────────────┼────────────────────┘
                            │
                            ▼
                   ┌─────────────────┐
                   │  Flask Server   │
                   │    (app.py)     │
                   └────────┬────────┘
                            │
              ┌─────────────┼─────────────┐
              ▼             ▼             ▼
        ┌──────────┐  ┌──────────┐  ┌──────────┐
        │  Browser │  │   CSV    │  │  Frames  │
        │ (Streams)│  │   Log    │  │  (JPEG)  │
        └──────────┘  └──────────┘  └──────────┘
```

```
┌─────────────────────────────────────────────────────────────────────────────────────────┐
│                          IPcam_stream - System Overview                                  │
│                    Cattle Monitoring & RFID Capture System                              │
└─────────────────────────────────────────────────────────────────────────────────────────┘


                                    ┌─────────────────────┐
                                    │    WEB BROWSER      │
                                    │  (Live Dashboard)   │
                                    │                     │
                                    │  • View 3 streams   │
                                    │  • Click for temp   │
                                    │  • Add/remove cams  │
                                    └──────────┬──────────┘
                                               │
                                               ▼
┌─────────────────────────────────────────────────────────────────────────────────────────┐
│                                                                                          │
│                              FLASK WEB SERVER (Python)                                   │
│                                    app.py                                                │
│                                                                                          │
│    ┌──────────────────┐   ┌──────────────────┐   ┌──────────────────┐                   │
│    │  Camera Manager  │   │   RGM Handler    │   │  RFID Capture    │                   │
│    │                  │   │                  │   │    System        │                   │
│    │ • Multi-camera   │   │ • USB thermal    │   │                  │                   │
│    │ • Dynamic add/   │   │ • Auto colormap  │   │ • Tag listener   │                   │
│    │   remove         │   │ • Center temp    │   │ • Frame grabber  │                   │
│    │ • Temp API       │   │                  │   │ • CSV logger     │                   │
│    └────────┬─────────┘   └────────┬─────────┘   └────────┬─────────┘                   │
│             │                      │                      │                              │
└─────────────┼──────────────────────┼──────────────────────┼──────────────────────────────┘
              │                      │                      │
              ▼                      ▼                      ▼
┌─────────────────────┐  ┌─────────────────────┐  ┌─────────────────────┐
│                     │  │                     │  │                     │
│  GEOVISION CAMERA   │  │   RGM THERMAL       │  │   AWR300 RFID       │
│   (IP Network)      │  │   (USB Camera)      │  │   (USB Serial)      │
│                     │  │                     │  │                     │
│  ┌───────────────┐  │  │  ┌───────────────┐  │  │  ┌───────────────┐  │
│  │  RGB Stream   │  │  │  │ Thermal View  │  │  │  │  Cattle EID   │  │
│  │  1080p/30fps  │  │  │  │ 256x192 px    │  │  │  │  15-digit ID  │  │
│  └───────────────┘  │  │  └───────────────┘  │  │  └───────────────┘  │
│  ┌───────────────┐  │  │  ┌───────────────┐  │  │                     │
│  │Thermal Stream │  │  │  │  Temperature  │  │  │  Scan triggers     │
│  │  + Temp API   │  │  │  │  at center    │  │  │  frame capture     │
│  └───────────────┘  │  │  └───────────────┘  │  │  from all cameras  │
│                     │  │                     │  │                     │
└─────────────────────┘  └─────────────────────┘  └──────────┬──────────┘
                                                             │
                                                             ▼
                                                  ┌─────────────────────┐
                                                  │                     │
                                                  │    DATA STORAGE     │
                                                  │                     │
                                                  │  📁 data/           │
                                                  │  ├── captures/      │
                                                  │  │   └── [frames]   │
                                                  │  └── cattle.csv     │
                                                  │                     │
                                                  └─────────────────────┘


═══════════════════════════════════════════════════════════════════════════════════════════
                                    WORKFLOW SUMMARY
═══════════════════════════════════════════════════════════════════════════════════════════

  ┌─────────────┐        ┌─────────────┐        ┌─────────────┐        ┌─────────────┐
  │   STREAM    │        │   MEASURE   │        │    SCAN     │        │    SAVE     │
  │             │        │             │        │             │        │             │
  │  Live video │   ──►  │ Click point │   ──►  │  RFID tag   │   ──►  │  Frames +   │
  │  from 3     │        │ get temp °C │        │  detected   │        │  temps to   │
  │  cameras    │        │             │        │             │        │  CSV        │
  └─────────────┘        └─────────────┘        └─────────────┘        └─────────────┘



```
---

## License

This project is provided as-is for educational and development purposes.
