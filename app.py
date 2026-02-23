"""Flask application exposing GeoVision and RGM streams side by side."""
from __future__ import annotations

import atexit
import os
import threading
from typing import Dict, Optional

from flask import Flask, Response, abort, jsonify, render_template, request

from geovision.config import DEFAULT_CREDENTIALS, RGB_STREAM, THERMAL_STREAM, CameraCredentials
from geovision.streams import RTSPStream
from geovision.aruco_stream import ArucoStream
from geovision.temperature import TemperatureClient
from rgm.streaming import RGMThermalStream


def create_streams(credentials: CameraCredentials) -> Dict[str, RTSPStream]:
    streams = {
        "rgb": RTSPStream(credentials, RGB_STREAM, "RGB"),
        "thermal": RTSPStream(credentials, THERMAL_STREAM, "Thermal"),
    }
    for stream in streams.values():
        stream.start()
    return streams


def str_to_bool(value: str) -> bool:
    return value.lower() in {"1", "true", "yes", "on"}


def create_rgm_stream() -> Optional[RGMThermalStream]:
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
    current_credentials = DEFAULT_CREDENTIALS
    streams = create_streams(current_credentials)
    rgm_stream = create_rgm_stream()

    # ArUco detection stream (RGB feed + marker overlay, detect every 10 frames)
    aruco_stream = ArucoStream(
        credentials=current_credentials,
        profile=RGB_STREAM,
        name="ArUco",
        detect_every_n=10,
    )
    aruco_stream.start()
    print("[ArUco] Detection stream initialized")

    @atexit.register
    def shutdown_streams() -> None:
        for stream in streams.values():
            stream.stop()
        if rgm_stream:
            rgm_stream.stop()
        aruco_stream.stop()

    @app.route("/")
    def index():
        return render_template(
            "index.html",
            rgm_available=rgm_stream is not None,
            geovision=current_credentials,
        )

    @app.route("/healthz")
    def healthz():
        return {"status": "ok"}

    @app.route("/temperature")
    def temperature():
        """Get temperature at a specific pixel coordinate."""
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
        framerate = RGB_STREAM.expected_fps if stream_name == "rgb" else THERMAL_STREAM.expected_fps
        return Response(
            stream.mjpeg_generator(framerate_hint=framerate),
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
        return Response(
            aruco_stream.mjpeg_generator(framerate_hint=RGB_STREAM.expected_fps),
            mimetype="multipart/x-mixed-replace; boundary=frame",
        )

    @app.route("/aruco/detections")
    def aruco_detections():
        """Return the latest ArUco detection results as JSON."""
        return jsonify(aruco_stream.latest_detections())

    @app.route("/rgm/center_temperature")
    def rgm_center_temperature():
        if rgm_stream is None:
            return jsonify({"error": "RGM camera not available"}), 503
        data = rgm_stream.latest_center()
        return jsonify(data)

    @app.route("/configure/geovision", methods=["POST"])
    def configure_geovision():
        nonlocal streams, current_credentials
        payload = request.get_json(silent=True) or request.form
        ip = (payload.get("ip") or "").strip()
        username = (payload.get("username") or "").strip()
        password = payload.get("password") or ""

        if not ip or not username:
            return jsonify({"status": "error", "message": "IP address and username are required"}), 400

        new_credentials = CameraCredentials(ip_address=ip, username=username, password=password)

        with config_lock:
            try:
                new_streams = create_streams(new_credentials)
            except Exception as exc:  # pragma: no cover - hardware dependent
                print(f"[GeoVision] Failed to apply new credentials: {exc}")
                return jsonify({"status": "error", "message": "Failed to connect with provided settings"}), 500

            old_streams = streams
            streams = new_streams
            current_credentials = new_credentials

        for stream in old_streams.values():
            stream.stop()

        return jsonify({"status": "ok", "message": "GeoVision credentials updated"})

    return app


app = create_app()


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000,use_reloader=False, debug=True)
