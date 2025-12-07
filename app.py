"""
Flask application for multi-camera GeoVision and RGM stream viewer.
Supports multiple GeoVision cameras with dynamic configuration.
"""
from __future__ import annotations

import atexit
import os
from typing import Optional

from flask import Flask, Response, abort, jsonify, render_template, request

from geovision.camera_manager import camera_manager
from geovision.config import THERMAL_STREAM
from rgm.streaming import RGMThermalStream


def str_to_bool(value: str) -> bool:
    return value.lower() in {"1", "true", "yes", "on"}


def create_rgm_stream() -> Optional[RGMThermalStream]:
    """Initialize local RGM thermal camera if available."""
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
    rgm_stream = create_rgm_stream()
    
    # Add default camera from environment variables if configured
    default_ip = os.getenv("GEOVISION_IP")
    if default_ip:
        try:
            camera_manager.add_camera(
                name=os.getenv("GEOVISION_NAME", "GeoVision Camera"),
                ip_address=default_ip,
                username=os.getenv("GEOVISION_USER", "admin"),
                password=os.getenv("GEOVISION_PASS", "admin123"),
                camera_id="default"
            )
        except Exception as e:
            print(f"[App] Failed to add default camera: {e}")

    @atexit.register
    def shutdown():
        camera_manager.shutdown()
        if rgm_stream:
            rgm_stream.stop()

    # ==================== Page Routes ====================
    
    @app.route("/")
    def index():
        """Main page with all camera streams."""
        cameras = camera_manager.get_camera_configs()
        return render_template(
            "index.html",
            cameras=cameras,
            rgm_available=rgm_stream is not None,
            thermal_api_coord_max=THERMAL_STREAM.sensor_width or 10000,
        )

    @app.route("/healthz")
    def healthz():
        return {"status": "ok"}

    # ==================== Camera Management API ====================
    
    @app.route("/api/cameras", methods=["GET"])
    def list_cameras():
        """List all configured cameras."""
        return jsonify({
            "cameras": camera_manager.get_camera_configs()
        })
    
    @app.route("/api/cameras", methods=["POST"])
    def add_camera():
        """Add a new camera."""
        data = request.get_json(silent=True) or request.form
        
        name = (data.get("name") or "").strip()
        ip_address = (data.get("ip_address") or data.get("ip") or "").strip()
        username = (data.get("username") or "").strip()
        password = data.get("password") or ""
        
        if not name:
            return jsonify({"error": "Camera name is required"}), 400
        if not ip_address:
            return jsonify({"error": "IP address is required"}), 400
        if not username:
            return jsonify({"error": "Username is required"}), 400
        
        try:
            config = camera_manager.add_camera(
                name=name,
                ip_address=ip_address,
                username=username,
                password=password
            )
            return jsonify({
                "status": "ok",
                "message": f"Camera '{name}' added successfully",
                "camera": config.to_dict()
            })
        except Exception as e:
            return jsonify({"error": str(e)}), 500
    
    @app.route("/api/cameras/<camera_id>", methods=["DELETE"])
    def remove_camera(camera_id: str):
        """Remove a camera."""
        print(f"[API] Delete request for camera: {camera_id}")
        
        # List available cameras for debugging
        available = [c['id'] for c in camera_manager.get_camera_configs()]
        print(f"[API] Available cameras before delete: {available}")
        
        if camera_manager.remove_camera(camera_id):
            print(f"[API] Successfully removed camera: {camera_id}")
            return jsonify({
                "status": "ok",
                "message": "Camera removed"
            })
        
        print(f"[API] Camera not found: {camera_id}")
        return jsonify({"error": "Camera not found"}), 404
    
    @app.route("/api/cameras/<camera_id>", methods=["PUT", "PATCH"])
    def update_camera(camera_id: str):
        """Update camera configuration."""
        data = request.get_json(silent=True) or request.form
        
        config = camera_manager.update_camera(
            camera_id=camera_id,
            name=data.get("name"),
            ip_address=data.get("ip_address") or data.get("ip"),
            username=data.get("username"),
            password=data.get("password")
        )
        
        if config:
            return jsonify({
                "status": "ok",
                "message": "Camera updated",
                "camera": config.to_dict()
            })
        return jsonify({"error": "Camera not found"}), 404

    # ==================== Video Streaming ====================
    
    @app.route("/video/<camera_id>/<stream_type>")
    def video_stream(camera_id: str, stream_type: str):
        """
        Stream video for a specific camera.
        
        Args:
            camera_id: Camera identifier
            stream_type: 'rgb' or 'thermal'
        """
        managed = camera_manager.get_camera(camera_id)
        if managed is None:
            abort(404, description=f"Camera '{camera_id}' not found")
        
        if stream_type == "rgb":
            stream = managed.rgb_stream
            fps = 30.0
        elif stream_type == "thermal":
            stream = managed.thermal_stream
            fps = 15.0
        else:
            abort(400, description=f"Invalid stream type: {stream_type}")
        
        if stream is None:
            abort(503, description=f"Stream not available for camera '{camera_id}'")
        
        return Response(
            stream.mjpeg_generator(framerate_hint=fps),
            mimetype="multipart/x-mixed-replace; boundary=frame",
        )

    @app.route("/video/rgm")
    def video_rgm():
        """RGM thermal camera stream."""
        if rgm_stream is None:
            abort(503, description="RGM camera not available")
        return Response(
            rgm_stream.mjpeg_generator(framerate_hint=15.0),
            mimetype="multipart/x-mixed-replace; boundary=frame",
        )

    # ==================== Temperature API ====================
    
    @app.route("/api/cameras/<camera_id>/temperature")
    def get_temperature(camera_id: str):
        """Get temperature at a specific pixel coordinate for a camera."""
        print(f"[Temperature API] Request for camera: {camera_id}")
        
        x = request.args.get("x", type=int)
        y = request.args.get("y", type=int)
        
        if x is None or y is None:
            print(f"[Temperature API] Missing coordinates: x={x}, y={y}")
            return jsonify({"error": "Missing x or y parameter"}), 400
        
        if x < 0 or y < 0:
            print(f"[Temperature API] Invalid coordinates: x={x}, y={y}")
            return jsonify({"error": "Coordinates must be non-negative"}), 400
        
        managed = camera_manager.get_camera(camera_id)
        if managed is None:
            print(f"[Temperature API] Camera not found: {camera_id}")
            # List available cameras for debugging
            available = [c['id'] for c in camera_manager.get_camera_configs()]
            print(f"[Temperature API] Available cameras: {available}")
            return jsonify({"error": f"Camera '{camera_id}' not found"}), 404
        
        print(f"[Temperature API] Camera: {camera_id}, Coords: ({x}, {y})")
        
        try:
            client = managed.get_temperature_client()
            result = client.get_dot_temperature(x, y)
            
            if result is None:
                print(f"[Temperature API] get_dot_temperature returned None")
                return jsonify({"error": "Failed to get temperature from camera"}), 500
            
            temp_c, resp_x, resp_y = result
            
            print(f"[Temperature API] Success: {temp_c}°C at ({resp_x}, {resp_y})")
            
            return jsonify({
                "temperature": round(temp_c, 2),
                "x": resp_x,
                "y": resp_y,
                "camera_id": camera_id
            })
        except Exception as e:
            print(f"[Temperature API] Exception: {e}")
            return jsonify({"error": f"Temperature request failed: {str(e)}"}), 500

    @app.route("/rgm/center_temperature")
    def rgm_center_temperature():
        """Get RGM center temperature."""
        if rgm_stream is None:
            return jsonify({"error": "RGM camera not available"}), 503
        return jsonify(rgm_stream.latest_center())

    # ==================== Thermal Info ====================
    
    @app.route("/thermal_info")
    def thermal_info():
        """Get thermal API configuration."""
        return jsonify({
            "api_coord_max": THERMAL_STREAM.sensor_width or 10000,
            "channel": THERMAL_STREAM.channel,
        })

    return app


app = create_app()


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000, use_reloader=False, debug=True)
