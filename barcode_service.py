"""Dedicated barcode detection service process."""
from __future__ import annotations

import atexit
import threading
from typing import Optional

from flask import Flask, Response, abort, jsonify, request

from geovision.barcode_stream import BarcodeStream
from geovision.config import DEFAULT_CREDENTIALS, RGB_STREAM, CameraCredentials
from geovision.streams import RTSPStream


def str_to_bool(value: str) -> bool:
    return value.lower() in {"1", "true", "yes", "on"}


def create_app() -> Flask:
    import os

    app = Flask(__name__)
    config_lock = threading.Lock()

    current_credentials = DEFAULT_CREDENTIALS
    rgb_stream = RTSPStream(current_credentials, RGB_STREAM, "BarcodeServiceRGB")
    rgb_stream.start()

    barcode_stream = BarcodeStream(
        source_stream=rgb_stream,
        name="BarcodeService",
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
    barcode_stream.start()
    print(f"[BarcodeService] Started on device {barcode_stream.inference_device}")

    @atexit.register
    def _shutdown() -> None:
        barcode_stream.stop()
        rgb_stream.stop()

    @app.route("/healthz")
    def healthz():
        return {"status": "ok", "device": barcode_stream.inference_device}

    @app.route("/video/barcode")
    def video_barcode():
        return Response(
            barcode_stream.mjpeg_generator(framerate_hint=None, jpeg_quality=70),
            mimetype="multipart/x-mixed-replace; boundary=frame",
        )

    @app.route("/barcode/detections")
    def barcode_detections():
        return jsonify(barcode_stream.latest_detections())

    @app.route("/configure/geovision", methods=["POST"])
    def configure_geovision():
        nonlocal rgb_stream, barcode_stream, current_credentials
        payload = request.get_json(silent=True) or request.form
        ip = (payload.get("ip") or "").strip()
        username = (payload.get("username") or "").strip()
        password = payload.get("password") or ""
        if not ip or not username:
            return jsonify({"status": "error", "message": "IP address and username are required"}), 400

        new_credentials = CameraCredentials(ip_address=ip, username=username, password=password)
        with config_lock:
            new_rgb = RTSPStream(new_credentials, RGB_STREAM, "BarcodeServiceRGB")
            new_rgb.start()
            new_barcode = BarcodeStream(
                source_stream=new_rgb,
                name="BarcodeService",
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
            new_barcode.start()

            old_rgb = rgb_stream
            old_barcode = barcode_stream
            rgb_stream = new_rgb
            barcode_stream = new_barcode
            current_credentials = new_credentials

        old_barcode.stop()
        old_rgb.stop()
        return jsonify({"status": "ok", "message": "Barcode service credentials updated"})

    return app


app = create_app()


if __name__ == "__main__":
    import os

    port = int(os.getenv("BARCODE_SERVICE_PORT", "8100"))
    debug = str_to_bool(os.getenv("BARCODE_SERVICE_DEBUG", "false"))
    app.run(host="127.0.0.1", port=port, use_reloader=False, debug=debug)
