"""Flask application exposing GeoVision and RGM streams side by side."""
from __future__ import annotations

import atexit
import os
import subprocess
import sys
import threading
from typing import Dict, Iterator, Optional

import requests
from flask import Flask, Response, abort, jsonify, render_template, request

from geovision.config import (
    DEFAULT_CREDENTIALS,
    RGB_PREVIEW_STREAM,
    RGB_STREAM,
    THERMAL_STREAM,
    CameraCredentials,
)
from geovision.streams import RTSPStream
from geovision.aruco_stream import ArucoStream
from geovision.barcode_stream import BarcodeStream
from geovision.temperature import TemperatureClient
from rgm.streaming import RGMThermalStream


def create_streams(credentials: CameraCredentials, enable_thermal: bool = True) -> Dict[str, RTSPStream]:
    streams = {
        "rgb": RTSPStream(credentials, RGB_PREVIEW_STREAM, "RGB"),
    }
    if enable_thermal:
        streams["thermal"] = RTSPStream(credentials, THERMAL_STREAM, "Thermal")
    for stream in streams.values():
        stream.start()
    return streams


def str_to_bool(value: str) -> bool:
    return value.lower() in {"1", "true", "yes", "on"}


def create_rgm_stream(enable_rgm: bool = True) -> Optional[RGMThermalStream]:
    if not enable_rgm:
        print("[RGM] Disabled (ENABLE_RGM=false)")
        return None
    try:
        stream = RGMThermalStream(
            device_index=int(os.getenv("RGM_DEVICE_INDEX", "0")),
            use_msmf=str_to_bool(os.getenv("RGM_USE_MSMF", "false")),
            view_scale=int(os.getenv("RGM_VIEW_SCALE", "3")),
            c_min_c=float(os.getenv("RGM_TEMP_MIN_C", "20.0")),
            c_max_c=float(os.getenv("RGM_TEMP_MAX_C", "40.0")),
        )
        stream.start()
        print("[RGM] Thermal camera initialized")
        return stream
    except Exception as exc:
        print(f"[RGM] Failed to initialize local thermal stream: {exc}")
        return None


def create_app() -> Flask:
    app = Flask(__name__)
    config_lock = threading.Lock()
    rgb_low_latency = str_to_bool(os.getenv("RGB_LOW_LATENCY", "true"))
    rgb_jpeg_quality = int(os.getenv("RGB_JPEG_QUALITY", "75"))
    enable_thermal = str_to_bool(os.getenv("ENABLE_THERMAL", "true"))
    enable_rgm = str_to_bool(os.getenv("ENABLE_RGM", "true"))
    current_credentials = DEFAULT_CREDENTIALS
    streams = create_streams(current_credentials, enable_thermal=enable_thermal)
    rgm_stream = create_rgm_stream(enable_rgm=enable_rgm)

    enable_aruco = str_to_bool(os.getenv("ENABLE_ARUCO", "false"))
    enable_barcode = str_to_bool(os.getenv("ENABLE_BARCODE", "true"))
    barcode_use_service = str_to_bool(os.getenv("BARCODE_USE_SERVICE", "true"))
    barcode_service_port = int(os.getenv("BARCODE_SERVICE_PORT", "8100"))
    barcode_service_base_url = os.getenv("BARCODE_SERVICE_URL", f"http://127.0.0.1:{barcode_service_port}")
    barcode_service_autostart = str_to_bool(os.getenv("BARCODE_SERVICE_AUTOSTART", "true"))
    rgb_preview_max_width = int(os.getenv("RGB_PREVIEW_MAX_WIDTH", "1280"))
    barcode_service_proc: Optional[subprocess.Popen] = None

    def create_aruco_stream(credentials: CameraCredentials) -> Optional[ArucoStream]:
        if not enable_aruco:
            return None
        stream = ArucoStream(
            credentials=credentials,
            profile=RGB_PREVIEW_STREAM,
            name="ArUco",
            detect_every_n=3,
        )
        stream.start()
        print("[ArUco] Detection stream initialized")
        return stream

    def create_barcode_stream(source_stream: RTSPStream) -> Optional[BarcodeStream]:
        if not enable_barcode:
            return None
        if barcode_use_service:
            return None
        stream = BarcodeStream(
            source_stream=source_stream,
            name="Barcode",
            model_path=os.getenv(
                "BARCODE_MODEL_PATH",
                "yolo_barcode_package/weights/YOLOV8s_Barcode_Detection.pt",
            ),
            device=os.getenv("BARCODE_DEVICE", "auto"),
            conf_threshold=float(os.getenv("BARCODE_CONF", "0.35")),
            imgsz=int(os.getenv("BARCODE_IMGSZ", "960")),
            enable_decode=str_to_bool(os.getenv("BARCODE_ENABLE_DECODE", "false")),
            detect_every_n_frames=int(os.getenv("BARCODE_DETECT_EVERY_N", "10")),
            cache_ttl_sec=float(os.getenv("BARCODE_CACHE_TTL_SEC", "2.0")),
            housekeeping_interval_sec=float(os.getenv("BARCODE_HOUSEKEEPING_SEC", "15.0")),
            release_cuda_cache=str_to_bool(os.getenv("BARCODE_RELEASE_CUDA_CACHE", "false")),
        )
        stream.start()
        print(f"[Barcode] Detection stream initialized on {stream.inference_device}")
        return stream

    def start_barcode_service_if_needed() -> None:
        nonlocal barcode_service_proc
        if not enable_barcode or not barcode_use_service or not barcode_service_autostart:
            return
        if barcode_service_proc is not None and barcode_service_proc.poll() is None:
            return
        service_script = os.path.join(os.path.dirname(__file__), "barcode_service.py")
        cmd = [sys.executable, service_script]
        env = os.environ.copy()
        env.setdefault("BARCODE_SERVICE_PORT", str(barcode_service_port))
        barcode_service_proc = subprocess.Popen(cmd, env=env)
        print(f"[Barcode] Started separate service on port {barcode_service_port}")

    def barcode_service_available(timeout: float = 0.6) -> bool:
        if not enable_barcode or not barcode_use_service:
            return False
        try:
            resp = requests.get(f"{barcode_service_base_url}/healthz", timeout=timeout)
            return resp.ok
        except requests.RequestException:
            return False

    def proxy_mjpeg(url: str) -> Iterator[bytes]:
        with requests.get(url, stream=True, timeout=(2.0, 60.0)) as upstream:
            upstream.raise_for_status()
            for chunk in upstream.iter_content(chunk_size=4096):
                if chunk:
                    yield chunk

    aruco_stream: Optional[ArucoStream] = None
    barcode_stream: Optional[BarcodeStream] = None
    start_barcode_service_if_needed()
    try:
        aruco_stream = create_aruco_stream(current_credentials)
    except Exception as exc:
        print(f"[ArUco] Failed to initialize: {exc}")
    try:
        barcode_stream = create_barcode_stream(streams["rgb"])
    except Exception as exc:
        print(f"[Barcode] Failed to initialize: {exc}")

    if not enable_aruco:
        print("[ArUco] Disabled (ENABLE_ARUCO=false)")
    if not enable_barcode:
        print("[Barcode] Disabled (ENABLE_BARCODE=false)")
    elif barcode_use_service:
        print(f"[Barcode] Using separate service: {barcode_service_base_url}")

    @atexit.register
    def shutdown_streams() -> None:
        for stream in streams.values():
            stream.stop()
        if rgm_stream:
            rgm_stream.stop()
        if aruco_stream:
            aruco_stream.stop()
        if barcode_stream:
            barcode_stream.stop()
        if barcode_service_proc is not None and barcode_service_proc.poll() is None:
            barcode_service_proc.terminate()

    @app.route("/")
    def index():
        if barcode_use_service:
            barcode_available = enable_barcode
        else:
            barcode_available = barcode_stream is not None
        return render_template(
            "index.html",
            rgm_available=rgm_stream is not None,
            aruco_available=aruco_stream is not None,
            barcode_available=barcode_available,
            thermal_available=("thermal" in streams),
            geovision=current_credentials,
        )

    @app.route("/healthz")
    def healthz():
        return {"status": "ok"}

    @app.route("/temperature")
    def temperature():
        """Get temperature at a specific pixel coordinate."""
        if "thermal" not in streams:
            return jsonify({"error": "Thermal stream disabled"}), 503
        x = request.args.get("x", type=int)
        y = request.args.get("y", type=int)
        
        if x is None or y is None:
            return jsonify({"error": "Missing x or y parameter"}), 400
        
        # Validate coordinates are non-negative
        if x < 0 or y < 0:
            print(f"[Temperature API] Invalid coordinates: x={x}, y={y} (must be non-negative)")
            return jsonify({"error": "Coordinates must be non-negative"}), 400
        
        # Log the request for debugging
        print(f"[Temperature API] Request received: x={x}, y={y}")
        
        client = TemperatureClient(credentials=current_credentials, channel=THERMAL_STREAM.channel)
        result = client.get_dot_temperature(x, y)
        
        if result is None:
            print(f"[Temperature API] Failed to get temperature for ({x}, {y})")
            return jsonify({"error": "Failed to get temperature"}), 500
        
        temp_c, resp_x, resp_y = result
        
        # Check if camera returned different coordinates
        coord_match = (resp_x == x and resp_y == y)
        if not coord_match:
            print(f"[Temperature API] Coordinate mismatch: requested ({x}, {y}), camera returned ({resp_x}, {resp_y})")
        else:
            print(f"[Temperature API] Coordinates match: ({x}, {y})")
        
        print(f"[Temperature API] Response: temp={temp_c:.2f}°C, x={resp_x}, y={resp_y} (requested: {x}, {y})")
        
        return jsonify({
            "temperature": round(temp_c, 2),
            "x": resp_x,
            "y": resp_y,
            "requested_x": x,  # Include requested coordinates for debugging
            "requested_y": y,
            "coordinates_match": coord_match
        })

    @app.route("/video/<stream_name>")
    def video(stream_name: str):
        stream = streams.get(stream_name)
        if stream is None:
            abort(404)
        if stream_name == "rgb":
            framerate = None if rgb_low_latency else RGB_PREVIEW_STREAM.expected_fps
            jpeg_quality = rgb_jpeg_quality
            max_width = rgb_preview_max_width
        else:
            framerate = THERMAL_STREAM.expected_fps
            jpeg_quality = 80
            max_width = None
        return Response(
            stream.mjpeg_generator(
                framerate_hint=framerate,
                jpeg_quality=jpeg_quality,
                max_width=max_width,
            ),
            mimetype="multipart/x-mixed-replace; boundary=frame",
        )

    @app.route("/video/rgm")
    def video_rgm():
        if rgm_stream is None:
            abort(503, description="RGM camera not available")
        return Response(
            rgm_stream.mjpeg_generator(framerate_hint=15.0),
            mimetype="multipart/x-mixed-replace; boundary=frame",
        )

    @app.route("/video/aruco")
    def video_aruco():
        """Annotated RGB stream with ArUco marker overlays."""
        if aruco_stream is None:
            abort(503, description="ArUco pipeline disabled")
        return Response(
            aruco_stream.mjpeg_generator(framerate_hint=None, jpeg_quality=70),
            mimetype="multipart/x-mixed-replace; boundary=frame",
        )

    @app.route("/aruco/detections")
    def aruco_detections():
        """Return the latest ArUco detection results as JSON."""
        if aruco_stream is None:
            return jsonify({"ids": [], "count": 0, "timestamp": 0.0, "disabled": True}), 503
        return jsonify(aruco_stream.latest_detections())

    @app.route("/video/barcode")
    def video_barcode():
        """Annotated RGB stream with YOLO barcode detections."""
        if barcode_use_service:
            try:
                return Response(
                    proxy_mjpeg(f"{barcode_service_base_url}/video/barcode"),
                    mimetype="multipart/x-mixed-replace; boundary=frame",
                )
            except requests.RequestException:
                abort(503, description="Barcode service unavailable")
        if barcode_stream is None:
            abort(503, description="Barcode pipeline disabled")
        return Response(
            barcode_stream.mjpeg_generator(framerate_hint=None, jpeg_quality=70),
            mimetype="multipart/x-mixed-replace; boundary=frame",
        )

    @app.route("/barcode/detections")
    def barcode_detections():
        """Return latest barcode detections."""
        if barcode_use_service:
            try:
                resp = requests.get(f"{barcode_service_base_url}/barcode/detections", timeout=1.0)
                if not resp.ok:
                    return jsonify(
                        {"ids": [], "count": 0, "timestamp": 0.0, "device": None, "disabled": True}
                    ), 503
                return jsonify(resp.json())
            except requests.RequestException:
                return jsonify(
                    {"ids": [], "count": 0, "timestamp": 0.0, "device": None, "disabled": True}
                ), 503
        if barcode_stream is None:
            return jsonify(
                {"ids": [], "count": 0, "timestamp": 0.0, "device": None, "disabled": True}
            ), 503
        return jsonify(barcode_stream.latest_detections())

    @app.route("/rgm/center_temperature")
    def rgm_center_temperature():
        if rgm_stream is None:
            return jsonify({"error": "RGM camera not available"}), 503
        data = rgm_stream.latest_center()
        return jsonify(data)

    @app.route("/configure/geovision", methods=["POST"])
    def configure_geovision():
        nonlocal streams, current_credentials, aruco_stream, barcode_stream
        payload = request.get_json(silent=True) or request.form
        ip = (payload.get("ip") or "").strip()
        username = (payload.get("username") or "").strip()
        password = payload.get("password") or ""

        if not ip or not username:
            return jsonify({"status": "error", "message": "IP address and username are required"}), 400

        new_credentials = CameraCredentials(ip_address=ip, username=username, password=password)

        with config_lock:
            try:
                new_streams = create_streams(new_credentials, enable_thermal=enable_thermal)
            except Exception as exc:  # pragma: no cover - hardware dependent
                print(f"[GeoVision] Failed to apply new credentials: {exc}")
                return jsonify({"status": "error", "message": "Failed to connect with provided settings"}), 500

            new_aruco = None
            new_barcode = None
            try:
                new_aruco = create_aruco_stream(new_credentials)
            except Exception as exc:
                print(f"[ArUco] Failed to restart after GeoVision config update: {exc}")
            if barcode_use_service:
                try:
                    requests.post(
                        f"{barcode_service_base_url}/configure/geovision",
                        json={
                            "ip": new_credentials.ip_address,
                            "username": new_credentials.username,
                            "password": new_credentials.password,
                        },
                        timeout=2.0,
                    )
                except requests.RequestException as exc:
                    print(f"[Barcode] Service credential sync failed: {exc}")
            else:
                try:
                    new_barcode = create_barcode_stream(new_streams["rgb"])
                except Exception as exc:
                    print(f"[Barcode] Failed to restart after GeoVision config update: {exc}")

            old_streams = streams
            old_aruco = aruco_stream
            old_barcode = barcode_stream
            streams = new_streams
            current_credentials = new_credentials
            aruco_stream = new_aruco
            barcode_stream = new_barcode

        for stream in old_streams.values():
            stream.stop()
        if old_aruco:
            old_aruco.stop()
        if old_barcode:
            old_barcode.stop()

        return jsonify({"status": "ok", "message": "GeoVision credentials updated"})

    return app


app = create_app()


if __name__ == "__main__":
    flask_debug = str_to_bool(os.getenv("FLASK_DEBUG", "false"))
    app.run(host="0.0.0.0", port=8000, use_reloader=False, debug=flask_debug)
