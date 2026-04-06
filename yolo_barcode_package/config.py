from dataclasses import dataclass
from pathlib import Path


PACKAGE_DIR = Path(__file__).resolve().parent
DEFAULT_WEIGHTS_PATH = PACKAGE_DIR / "weights" / "YOLOV8s_Barcode_Detection.pt"


@dataclass
class PipelineConfig:
    model_path: str = str(DEFAULT_WEIGHTS_PATH)
    device: str = "auto"  # auto | cuda:0 | mps | cpu
    conf_threshold: float = 0.5
    imgsz: int = 640
    enable_decode: bool = True
    min_box_size: int = 20
    pad_ratio_x: float = 0.18
    pad_ratio_y: float = 0.18
    use_roi_refine: bool = True
    max_decode_per_frame: int = 5
    fast_decode: bool = True
    retry_on_decode_fail: bool = True
    retry_pad_scale: float = 1.6
    save_output: bool = True
    save_preprocess_steps: bool = False
    save_metadata_txt: bool = True
    output_dir: str = "package_output_barcode"


@dataclass
class StreamConfig:
    # For 30 FPS stream, detect once/sec -> detect_every_n_frames=30
    detect_every_n_frames: int = 30
    cache_ttl_sec: float = 2.0
    iou_match_threshold: float = 0.5


@dataclass
class LiveConfig:
    # Capture/read behavior
    reconnect_backoff_sec: float = 1.0
    source_fps_fallback: float = 30.0
    poll_sleep_sec: float = 0.002

    # Output behavior
    save_annotated_video: bool = True
    save_session_json: bool = True
    output_dir: str = "package_output_live"

    # Display behavior
    display_live: bool = True
    display_window_name: str = "yolo_barcode_live"
    display_scale: float = 1.0

    # Session log behavior
    interval_gap_close_sec: float = 1.5
