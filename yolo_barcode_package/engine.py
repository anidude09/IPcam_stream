from typing import Any, Dict, List, Tuple

import numpy as np

from .config import PipelineConfig, StreamConfig
from .core import BarcodeCorePipeline, CoreConfig
from .stream import BarcodeStreamEngine, StreamRuntime


class YoloBarcodeEngine:
    """
    Unified package API.

    - process_frame(frame): decode from numpy frame
    - process_image_path(path): decode from image file path
    - process_stream_frame(frame): decode with stream cadence/cache rules
    """

    def __init__(self, pipeline_cfg: PipelineConfig, stream_cfg: StreamConfig | None = None):
        core_cfg = CoreConfig(
            device=pipeline_cfg.device,
            conf_threshold=pipeline_cfg.conf_threshold,
            imgsz=pipeline_cfg.imgsz,
            enable_decode=pipeline_cfg.enable_decode,
            min_box_size=pipeline_cfg.min_box_size,
            pad_ratio_x=pipeline_cfg.pad_ratio_x,
            pad_ratio_y=pipeline_cfg.pad_ratio_y,
            use_roi_refine=pipeline_cfg.use_roi_refine,
            max_decode_per_frame=pipeline_cfg.max_decode_per_frame,
            fast_decode=pipeline_cfg.fast_decode,
            retry_on_decode_fail=pipeline_cfg.retry_on_decode_fail,
            retry_pad_scale=pipeline_cfg.retry_pad_scale,
            save_output=pipeline_cfg.save_output,
            save_preprocess_steps=pipeline_cfg.save_preprocess_steps,
            output_dir=pipeline_cfg.output_dir,
        )
        self.pipeline_cfg = pipeline_cfg
        self.pipeline = BarcodeCorePipeline(pipeline_cfg.model_path, core_cfg)
        self.stream = None
        if stream_cfg is not None:
            s_cfg = StreamRuntime(
                detect_every_n_frames=stream_cfg.detect_every_n_frames,
                cache_ttl_sec=stream_cfg.cache_ttl_sec,
                iou_match_threshold=stream_cfg.iou_match_threshold,
            )
            self.stream = BarcodeStreamEngine(self.pipeline, s_cfg)

    def process_frame(self, frame: np.ndarray, frame_tag: str | None = None) -> Tuple[np.ndarray, List[Dict[str, Any]]]:
        return self.pipeline.process_frame(frame, frame_tag=frame_tag)

    def process_image_path(self, image_path: str) -> Tuple[np.ndarray, List[Dict[str, Any]]]:
        import cv2

        img = cv2.imread(image_path)
        if img is None:
            raise ValueError(f"Could not read image: {image_path}")
        return self.process_frame(img, frame_tag=image_path.split("/")[-1].split(".")[0])

    def process_stream_frame(self, frame: np.ndarray) -> Tuple[np.ndarray, List[Dict[str, Any]]]:
        if self.stream is None:
            raise RuntimeError("Stream config not provided. Initialize with StreamConfig.")
        return self.stream.process(frame)

    def process_rtsp(
        self,
        rtsp_url: str,
        max_frames: int | None = None,
        display: bool = False,
        window_name: str = "yolo_barcode",
    ):
        """
        Convenience loop for direct RTSP processing.
        Returns list of per-frame decode outputs.
        """
        import cv2

        if self.stream is None:
            raise RuntimeError("Stream config not provided. Initialize with StreamConfig.")

        cap = cv2.VideoCapture(rtsp_url)
        if not cap.isOpened():
            raise RuntimeError(f"Could not open RTSP stream: {rtsp_url}")

        outputs: List[Dict[str, Any]] = []
        frame_idx = 0
        try:
            while True:
                ok, frame = cap.read()
                if not ok:
                    break
                vis, results = self.process_stream_frame(frame)
                outputs.append({"frame_idx": frame_idx, "results": results})
                frame_idx += 1
                if display:
                    cv2.imshow(window_name, vis)
                    if cv2.waitKey(1) & 0xFF == ord("q"):
                        break
                if max_frames is not None and frame_idx >= max_frames:
                    break
        finally:
            cap.release()
            if display:
                cv2.destroyAllWindows()
        return outputs
