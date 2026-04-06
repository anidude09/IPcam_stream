"""
Editable package-level settings for quick testing/debugging.
"""

from .config import LiveConfig, PipelineConfig, StreamConfig

# Input source for image runner (single file or directory)
INPUT_SOURCE = "barcode_images"
RTSP_URL = "rtsp://username:password@camera-ip:554/stream"

# Core pipeline parameters
PIPELINE = PipelineConfig(
    model_path="yolo_barcode_package/weights/YOLOV8s_Barcode_Detection.pt",
    device="auto",
    conf_threshold=0.5,
    imgsz=1280,
    enable_decode=False,
    min_box_size=20,
    pad_ratio_x=0.18,
    pad_ratio_y=0.18,
    use_roi_refine=True,
    max_decode_per_frame=5,
    fast_decode=True,
    retry_on_decode_fail=True,
    retry_pad_scale=1.6,
    save_output=True,
    save_preprocess_steps=False,
    save_metadata_txt=True,
    output_dir="package_output_barcode",
)

# Streaming runtime behavior
STREAM = StreamConfig(
    detect_every_n_frames=30,  # 30 FPS stream -> detect once per second
    cache_ttl_sec=2.0,
    iou_match_threshold=0.5,
)

LIVE = LiveConfig(
    reconnect_backoff_sec=1.0,
    source_fps_fallback=30.0,
    poll_sleep_sec=0.002,
    save_annotated_video=True,
    save_session_json=True,
    output_dir="package_output_live",
    display_live=True,
    display_window_name="yolo_barcode_live",
    display_scale=0.8,
    interval_gap_close_sec=1.5,
)
