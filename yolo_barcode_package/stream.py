import time
from dataclasses import dataclass
from typing import Dict, List

import cv2
import numpy as np

from .core import BarcodeCorePipeline


@dataclass
class StreamRuntime:
    detect_every_n_frames: int = 30
    cache_ttl_sec: float = 2.0
    iou_match_threshold: float = 0.5


class BarcodeStreamEngine:
    def __init__(self, pipeline: BarcodeCorePipeline, runtime: StreamRuntime):
        self.pipeline = pipeline
        self.runtime = runtime
        self.frame_idx = 0
        self._last_detections: List[Dict] = []
        self._last_detect_ts: float = 0.0

    def process(self, frame: np.ndarray):
        self.frame_idx += 1
        run_detect = (self.frame_idx % self.runtime.detect_every_n_frames) == 1
        if run_detect:
            vis, results = self.pipeline.process_frame(frame, frame_tag=f"frame_{self.frame_idx:06d}")
            now = time.time()
            self._last_detections = [
                {
                    "bbox": r["bbox"],
                    "confidence": r.get("confidence", 0.0),
                    "extracted_id": r.get("extracted_id"),
                }
                for r in results
            ]
            self._last_detect_ts = now
            return vis, results

        vis = frame.copy()
        pseudo_results = []
        # Reuse last detections between heavy YOLO runs to keep overlays visible.
        for det in self._last_detections:
            x1, y1, x2, y2 = det["bbox"]
            conf = float(det.get("confidence", 0.0))
            extracted_id = det.get("extracted_id")
            label = (
                f"{extracted_id} ({conf:.2f})"
                if extracted_id is not None
                else f"barcode ({conf:.2f})"
            )
            pseudo_results.append(
                {
                    "bbox": det["bbox"],
                    "extracted_id": extracted_id,
                    "confidence": conf,
                }
            )
            cv2.rectangle(vis, (x1, y1), (x2, y2), (0, 255, 0), 2)
            cv2.putText(
                vis,
                label,
                (x1, y1 - 10),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.7,
                (0, 255, 0),
                2,
            )
        return vis, pseudo_results
