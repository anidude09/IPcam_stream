"""Flask application exposing RGB and thermal streams side by side."""
from __future__ import annotations

import atexit
from typing import Dict

from flask import Flask, Response, abort, render_template

from geovision.config import DEFAULT_CREDENTIALS, RGB_STREAM, THERMAL_STREAM
from geovision.streams import RTSPStream


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
