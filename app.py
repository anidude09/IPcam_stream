"""Flask application exposing RGB and thermal streams side by side."""
from __future__ import annotations

import atexit
from typing import Dict

from flask import Flask, Response, abort, jsonify, render_template, request

from geovision.config import DEFAULT_CREDENTIALS, RGB_STREAM, THERMAL_STREAM
from geovision.streams import RTSPStream
from geovision.temperature import TemperatureClient


def create_streams() -> Dict[str, RTSPStream]:
    streams = {
        "rgb": RTSPStream(DEFAULT_CREDENTIALS, RGB_STREAM, "RGB"),
        "thermal": RTSPStream(DEFAULT_CREDENTIALS, THERMAL_STREAM, "Thermal"),
    }
    for stream in streams.values():
        stream.start()
    return streams


def create_app() -> Flask:
    app = Flask(__name__)
    streams = create_streams()

    @atexit.register
    def shutdown_streams() -> None:
        for stream in streams.values():
            stream.stop()

    @app.route("/")
    def index():
        return render_template("index.html")

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
        
        client = TemperatureClient(credentials=DEFAULT_CREDENTIALS, channel=THERMAL_STREAM.channel)
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

    return app


app = create_app()


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000, debug=True)
