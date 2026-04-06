# GeoVision Camera Setup

> **This guide is for first-time users** who have just received a GeoVision thermal/RGB IP camera and need to go from unboxing to a working RTSP stream.

---

## Table of Contents

1. [What's in the Box](#1-whats-in-the-box)
2. [Physical Connections](#2-physical-connections)
3. [Finding the Camera on Your Network](#3-finding-the-camera-on-your-network)
4. [Accessing the Camera Web Admin](#4-accessing-the-camera-web-admin)
5. [Network Configuration](#5-network-configuration)
6. [Understanding RTSP Stream Profiles](#6-understanding-rtsp-stream-profiles)
7. [Enabling the Thermal Channel](#7-enabling-the-thermal-channel)
8. [Temperature API Setup](#8-temperature-api-setup)
9. [Verifying Streams with VLC](#9-verifying-streams-with-vlc)
10. [Credentials & Security](#10-credentials--security)

---

## 1. What's in the Box

A typical GeoVision thermal camera package includes:

- The camera unit itself (with RGB + thermal sensors)
- Power adapter or PoE injector
- Ethernet cable
- Mounting hardware
- Quick-start card with default credentials

> **Camera model:** <!-- TODO: Add your specific GeoVision model number here (e.g. GV-TBL4711) -->
>
> _Replace with your model once confirmed._

---

## 2. Physical Connections

### Power

The camera can be powered in two ways:

| Method | When to use |
|---|---|
| **PoE (Power over Ethernet)** | Preferred — single Ethernet cable carries both data and power. Requires a PoE switch or PoE injector (IEEE 802.3af/at). |
| **DC Power Adapter** | If your network switch does not support PoE. Use the barrel-jack adapter included in the box. |

### Ethernet

Connect the camera's RJ-45 Ethernet port to your local network switch or directly to your PC:

```
[Camera] ──── Ethernet ──── [PoE Switch / Router] ──── [Your PC]
```

> **Tip:** For bench testing, you can connect the camera directly to your PC with a crossover cable (or any modern Ethernet cable — most NICs support auto-MDI/X). Just make sure your PC's network adapter is on the same subnet.

---

## 3. Finding the Camera on Your Network

### Default IP Address

Most GeoVision cameras ship with a factory-default IP of:

```
192.168.0.10
```

If your PC is on a different subnet (e.g. `192.168.1.x`), you'll need to either:
- Temporarily change your PC's IP to `192.168.0.x` (e.g. `192.168.0.100`), or
- Use the GeoVision IP Installer tool.

### GeoVision IP Installer Utility

GeoVision provides a free Windows utility called **GV-IP Device Utility** (sometimes labelled "GV-IP Installer" or "IP Finder"):

1. Download it from the [GeoVision Downloads page](https://www.geovision.com.tw/download/product/)
2. Run the utility — it broadcasts a Layer 2 discovery packet and lists all GeoVision devices on your LAN regardless of subnet
3. Select your camera and note its current IP

<!-- TODO: Screenshot of GV-IP Device Utility showing discovered camera -->

### Alternative: nmap / arp-scan

On a Linux or advanced Windows setup you can scan the local subnet:

```bash
nmap -sn 192.168.0.0/24
```

Look for a device with a MAC address starting with the GeoVision OUI prefix.

---

## 4. Accessing the Camera Web Admin

Once you know the camera's IP, open a browser:

```
http://192.168.0.10
```

Log in with the factory credentials:

| Field | Default |
|---|---|
| Username | `admin` |
| Password | `admin` or `admin123` (model-dependent) |

> **⚠️ Change these defaults immediately** — see [Credentials & Security](#10-credentials--security).

<!-- TODO: Screenshot of camera login page -->

After logging in you'll see the camera's web admin dashboard with live preview and settings tabs.

<!-- TODO: Screenshot of camera admin dashboard overview -->

---

## 5. Network Configuration

To assign a static IP that fits your network:

1. Navigate to **Settings → Network → TCP/IP** (path varies by firmware version)
2. Disable DHCP
3. Set:
   - **IP Address**: e.g. `192.168.0.10` (or whatever fits your LAN)
   - **Subnet Mask**: `255.255.255.0`
   - **Default Gateway**: your router's IP
4. Click **Save** / **Apply**
5. The camera will reboot — reconnect at the new IP

<!-- TODO: Screenshot of camera network settings page -->

> **Important:** After changing the IP, update the `GEOVISION_IP` environment variable (or the web UI settings form) in this toolkit to match.

---

## 6. Understanding RTSP Stream Profiles

GeoVision cameras expose multiple RTSP stream profiles. This toolkit uses three of them:

| Profile | RTSP Path | Resolution | FPS | Channel | Used For |
|---|---|---|---|---|---|
| **profile1** | `/profile1` | Full HD (e.g. 1920×1080) | 30 | 1 (RGB) | Barcode detection (needs high res) |
| **profile2** | `/profile2` | Lower (e.g. 640×480) | 30 | 1 (RGB) | Web UI preview, ArUco detection |
| **profile4** | `/profile4` | Thermal resolution (e.g. 384×288) | 15 | 2 (Thermal) | Thermal stream & temperature overlay |

### RTSP URL Format

```
rtsp://<username>:<password>@<camera-ip>:554/<profile>
```

**Examples:**

```
rtsp://admin:admin123@192.168.0.10:554/profile1   # Full HD RGB
rtsp://admin:admin123@192.168.0.10:554/profile2   # Preview RGB
rtsp://admin:admin123@192.168.0.10:554/profile4   # Thermal
```

### Configuring Profiles in the Camera Admin

1. Navigate to **Settings → Video → Stream** (or similar)
2. For each profile you can set:
   - **Resolution** (e.g. 1920×1080 for profile1, 640×480 for profile2)
   - **Frame rate** (e.g. 30 for RGB, 15 for thermal)
   - **Bitrate** and **Encoding** (H.264 recommended for RTSP compatibility)
   - **Channel** assignment (Channel 1 = RGB sensor, Channel 2 = Thermal sensor)

<!-- TODO: Screenshot of camera stream profile settings -->

> **Tip:** If you customize profile assignments, update the environment variables `GEOVISION_RGB_PROFILE`, `GEOVISION_RGB_PREVIEW_PROFILE`, and `GEOVISION_THERMAL_PROFILE` accordingly. See [Configuration Reference](configuration.md).

---

## 7. Enabling the Thermal Channel

On dual-sensor GeoVision cameras:

- **Channel 1** = RGB (visible light) sensor
- **Channel 2** = Thermal (infrared) sensor

Make sure the thermal channel is enabled:

1. Navigate to **Settings → Video** or **Settings → Thermal**
2. Confirm Channel 2 is active
3. Verify that `profile4` is mapped to Channel 2

<!-- TODO: Screenshot of thermal channel settings -->

### Thermal Resolution

Thermal sensor resolution is typically much lower than RGB (e.g. 384×288 or 256×192). This is normal — it's a hardware limitation of uncooled thermal microbolometer sensors. The toolkit's overlay system accounts for this smaller resolution.

---

## 8. Temperature API Setup

The toolkit uses the camera's built-in HTTP temperature API to query pixel-level temperatures. Two endpoints are used:

### GetDotTemperature

Query the temperature at a specific (x, y) pixel coordinate on the thermal image:

```
POST http://<camera-ip>/GetDotTemperature/<channel>
Content-Type: application/xml
Authorization: Basic (admin credentials)
```

**Request body (XML):**

```xml
<?xml version="1.0" encoding="UTF-8"?>
<config version="1.0" xmlns="http://www.ipc.com/ver10">
    <dotTemperature>
        <hotX>192</hotX>
        <hotY>144</hotY>
    </dotTemperature>
</config>
```

**Response:**

The camera returns an XML response with:
- `<temperature>` — raw value in **hundredths of °C** (e.g. `2835` = 28.35 °C)
- `<hotX>` / `<hotY>` — confirmed pixel coordinates

### GetTemperatureCurrentInfo

Query ROI (Region of Interest) temperature statistics:

```
GET http://<camera-ip>/GetTemperatureCurrentInfo/<channel>
Authorization: Basic (admin credentials)
```

Returns min, max, and average temperatures for configured ROIs.

### Enabling the Temperature API

On some GeoVision models, the temperature measurement API requires enabling in the camera admin:

1. Navigate to **Settings → Thermal → Temperature Measurement** (or **Intelligent Analysis → Temperature**)
2. Enable **Temperature Measurement**
3. Optionally configure ROI regions for the `GetTemperatureCurrentInfo` endpoint

<!-- TODO: Screenshot of temperature measurement settings -->

> **Note:** The temperature API uses HTTP Basic Authentication with the same credentials as the admin panel.

---

## 9. Verifying Streams with VLC

Before running the toolkit, confirm your RTSP streams work independently:

1. Open [VLC media player](https://www.videolan.org/vlc/)
2. Go to **Media → Open Network Stream**
3. Enter the RTSP URL:

```
rtsp://admin:admin123@192.168.0.10:554/profile2
```

4. Click **Play** — you should see the live camera feed

Repeat for each profile:

| Test | URL |
|---|---|
| RGB full-res | `rtsp://admin:admin123@192.168.0.10:554/profile1` |
| RGB preview | `rtsp://admin:admin123@192.168.0.10:554/profile2` |
| Thermal | `rtsp://admin:admin123@192.168.0.10:554/profile4` |

If any stream fails:
- Check credentials
- Verify the profile exists in the camera admin
- Try adding `?tcp` to force TCP transport: `rtsp://...@192.168.0.10:554/profile2?tcp`
- See [Troubleshooting](troubleshooting.md)

---

## 10. Credentials & Security

### Change Default Passwords

**Always change the factory default credentials** before deploying:

1. Log into the camera web admin
2. Navigate to **Settings → System → User Management**
3. Change the admin password

<!-- TODO: Screenshot of user management page -->

### How Credentials Are Used

This toolkit passes credentials in three places:

| Protocol | Format | Example |
|---|---|---|
| **RTSP** | Embedded in URL | `rtsp://admin:pass@192.168.0.10:554/profile1` |
| **HTTP (temperature API)** | HTTP Basic auth header | `Authorization: Basic base64(admin:pass)` |
| **Toolkit config** | Environment variables or web UI form | `GEOVISION_USER=admin` |

> **⚠️ Security note:** RTSP URLs contain plaintext credentials. Ensure the camera and this toolkit run on a trusted local network. Do not expose the RTSP ports to the internet.

---

## Next Steps

Once your camera is set up and streams are verified:

1. [Install the toolkit](installation.md)
2. [Run the dashboard](quick-start.md)
3. [Explore the web UI](web-ui-guide.md)
