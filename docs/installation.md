# Installation

## Prerequisites

| Requirement | Details |
|---|---|
| **Operating System** | Windows 10/11 (tested). Linux and macOS should work for the core functionality, but the RGM USB thermal camera helpers target Windows backends (DirectShow / MSMF). |
| **Python** | 3.9 or newer (3.11+ recommended) |
| **Network** | GeoVision camera reachable from your machine (same LAN or routed) |
| **GPU (optional)** | NVIDIA GPU with CUDA support significantly accelerates the YOLO barcode detection pipeline. Without a GPU, inference falls back to CPU. |

### Native Dependencies

Some Python packages require native libraries:

| Package | Native dependency | Notes |
|---|---|---|
| `opencv-python` | Bundled | Installs automatically via pip |
| `pyzbar` | `zbar` shared library | On Windows, pyzbar bundles the DLL. On Linux, install `libzbar0`: `sudo apt install libzbar0` |
| `zxing-cpp` | C++ ZXing library | Pre-built wheels available for most platforms via pip |
| `torch` | CUDA toolkit (optional) | For GPU inference. CPU-only torch works fine for smaller workloads. Install the correct torch variant from [pytorch.org](https://pytorch.org/get-started/locally/) |
| `ultralytics` | — | YOLO framework; pulls in torch if not already installed |

---

## Step-by-Step Setup

### 1. Clone or Download the Repository

```powershell
git clone https://github.com/anidude09/IPcam_stream.git
cd IPcam_stream
```

### 2. Create a Virtual Environment

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

> **Linux / macOS:**
> ```bash
> python3 -m venv .venv
> source .venv/bin/activate
> ```

### 3. Install Dependencies

```powershell
pip install -r requirements.txt
```

This installs:

| Category | Packages |
|---|---|
| Web framework | Flask, Werkzeug, Jinja2, click, blinker |
| Computer vision | opencv-python, numpy |
| HTTP client | requests, urllib3, certifi |
| ML / barcode | ultralytics, torch, pyzbar, zxing-cpp |

### 4. (Optional) Install GPU-Accelerated PyTorch

If you have an NVIDIA GPU and want faster barcode detection:

```powershell
# Uninstall CPU-only torch first
pip uninstall torch torchvision torchaudio

# Install CUDA-enabled torch (adjust cu12x to your CUDA version)
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu121
```

Verify:

```python
import torch
print(torch.cuda.is_available())   # Should print True
print(torch.cuda.get_device_name()) # e.g. "NVIDIA GeForce RTX 3060"
```

### 5. Verify YOLO Weights Exist

The barcode detection model is bundled at:

```
yolo_barcode_package/weights/YOLOV8s_Barcode_Detection.pt
```

This file (~22 MB) should already be present in the repository. If it's missing, the barcode detection pipeline will fail to start.

---

## Directory Structure After Installation

```
IPcam_stream/
├── .venv/                      # Virtual environment (git-ignored)
├── app.py                      # Main Flask application
├── barcode_service.py          # Separate barcode detection process
├── demo.py                     # Simple RGB stream viewer
├── record_test.py              # Dual-stream recorder
├── temp_test.py                # Interactive thermal viewer
├── temperature_api_test.py     # CLI temperature API probe
├── requirements.txt            # Python dependencies
├── geovision/                  # GeoVision camera package
├── rgm/                        # RGM USB thermal sensor package
├── yolo_barcode_package/       # YOLO barcode detection package
├── templates/                  # Jinja2 HTML templates
├── static/                     # CSS + JavaScript
├── docs/                       # This documentation
├── data/                       # Captured data (recordings, etc.)
└── records/                    # Recording output directory
```

---

## Next Steps

→ [Quick Start](quick-start.md) — run the dashboard  
→ [Configuration Reference](configuration.md) — customize behavior with environment variables
