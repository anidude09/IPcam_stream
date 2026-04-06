"""Threaded barcode detection stream fed from an existing RGB stream."""
from __future__ import annotations

import cv2
import gc
import threading
import time
from typing import Any, Dict, List, Optional

import numpy as np
try:
    import torch
except Exception:  # pragma: no cover - optional dependency at runtime
    torch = None

from .streams import RTSPStream
from yolo_barcode_package import PipelineConfig, StreamConfig, YoloBarcodeEngine


class BarcodeStream:
    """YOLO barcode stream that reuses frames from a source RTSPStream."""

    def __init__(
        self,
        source_stream: RTSPStream,
        name: str = "Barcode",
        model_path: str = "yolo_barcode_package/weights/YOLOV8s_Barcode_Detection.pt",
        device: str = "auto",
        conf_threshold: float = 0.5,
        imgsz: int = 640,
        enable_decode: bool = False,
        detect_every_n_frames: int = 30,
        cache_ttl_sec: float = 2.0,
        poll_sleep_sec: float = 0.01,
        housekeeping_interval_sec: float = 15.0,
        release_cuda_cache: bool = False,
    ) -> None:
        self.name = name
        self.source_stream = source_stream
        self.poll_sleep_sec = poll_sleep_sec
        self.housekeeping_interval_sec = max(0.0, float(housekeeping_interval_sec))
        self.release_cuda_cache = release_cuda_cache
        self._next_housekeeping_ts = time.time() + self.housekeeping_interval_sec

        pipeline_cfg = PipelineConfig(
            model_path=model_path,
            device=device,
            conf_threshold=conf_threshold,
            imgsz=imgsz,
            enable_decode=enable_decode,
            save_output=False,
            save_preprocess_steps=False,
            save_metadata_txt=False,
        )
        stream_cfg = StreamConfig(
            detect_every_n_frames=max(1, int(detect_every_n_frames)),
            cache_ttl_sec=cache_ttl_sec,
            iou_match_threshold=0.5,
        )
        self._engine = YoloBarcodeEngine(pipeline_cfg=pipeline_cfg, stream_cfg=stream_cfg)
        self._inference_device = self._engine.pipeline.device

        self._running = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._lock = threading.Lock()
        self._latest_frame: Optional[np.ndarray] = None
        self._frame_id: int = 0
        self._jpeg_cache_lock = threading.Lock()
        self._jpeg_cache: Dict[int, tuple[int, bytes]] = {}
        self._det_lock = threading.Lock()
        self._last_results: List[Dict[str, Any]] = []
        self._last_detection_ts: float = 0.0

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._running.set()
        self._thread = threading.Thread(
            target=self._process_loop,
            name=f"BarcodeStream-{self.name}",
            daemon=True,
        )
        self._thread.start()

    def stop(self) -> None:
        self._running.clear()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=2.0)
        self._thread = None

    @property
    def inference_device(self) -> str:
        return self._inference_device

    def latest_frame(self, copy: bool = True) -> Optional[np.ndarray]:
        with self._lock:
            if self._latest_frame is None:
                return None
            return self._latest_frame.copy() if copy else self._latest_frame

    def _set_latest_frame(self, frame: np.ndarray) -> None:
        with self._lock:
            self._latest_frame = frame
            self._frame_id += 1

    def mjpeg_generator(
        self,
        framerate_hint: Optional[float] = None,
        jpeg_quality: int = 70,
    ):
        delay = 1.0 / framerate_hint if framerate_hint and framerate_hint > 0 else 0.0
        encode_params = [cv2.IMWRITE_JPEG_QUALITY, jpeg_quality]
        last_sent_frame_id = -1
        while self._running.is_set():
            with self._lock:
                if self._latest_frame is None:
                    frame = None
                    frame_id = -1
                else:
                    if self._frame_id == last_sent_frame_id:
                        frame = None
                    else:
                        frame = self._latest_frame.copy()
                    frame_id = self._frame_id
            if frame is None:
                time.sleep(0.002)
                continue

            encoded_bytes: Optional[bytes] = None
            with self._jpeg_cache_lock:
                cached = self._jpeg_cache.get(jpeg_quality)
                if cached and cached[0] == frame_id:
                    encoded_bytes = cached[1]
            if encoded_bytes is None:
                success, encoded = cv2.imencode(".jpg", frame, encode_params)
                if not success:
                    continue
                encoded_bytes = encoded.tobytes()
                with self._jpeg_cache_lock:
                    self._jpeg_cache[jpeg_quality] = (frame_id, encoded_bytes)

            yield (
                b"--frame\r\n"
                b"Content-Type: image/jpeg\r\n\r\n" + encoded_bytes + b"\r\n"
            )
            last_sent_frame_id = frame_id

            if delay:
                time.sleep(delay)

    def latest_detections(self) -> Dict[str, Any]:
        with self._det_lock:
            ids = sorted(
                {
                    str(item.get("extracted_id"))
                    for item in self._last_results
                    if item.get("extracted_id") is not None
                }
            )
            detection_count = len(self._last_results)
            return {
                "ids": ids,
                "count": detection_count,
                "decoded_count": len(ids),
                "timestamp": self._last_detection_ts,
                "device": self._inference_device,
            }

    def _process_loop(self) -> None:
        last_frame_ref = None
        while self._running.is_set():
            frame_ref = self.source_stream.latest_frame(copy=False)
            if frame_ref is None:
                time.sleep(self.poll_sleep_sec)
                continue

            if frame_ref is last_frame_ref:
                time.sleep(self.poll_sleep_sec)
                continue
            last_frame_ref = frame_ref
            frame = frame_ref.copy()

            try:
                vis, results = self._engine.process_stream_frame(frame)
            except Exception as exc:
                print(f"[Barcode] Inference error: {exc}")
                vis = frame
                results = []

            with self._det_lock:
                self._last_results = list(results)
                self._last_detection_ts = time.time()

            self._set_latest_frame(vis)

            if (
                self.housekeeping_interval_sec > 0.0
                and time.time() >= self._next_housekeeping_ts
            ):
                self._run_housekeeping()
                self._next_housekeeping_ts = time.time() + self.housekeeping_interval_sec

    def _run_housekeeping(self) -> None:
        # Reclaim unreachable Python objects.
        gc.collect()

        # Keep only current encoded frame bytes for each quality key.
        with self._jpeg_cache_lock:
            if len(self._jpeg_cache) > 4:
                items = list(self._jpeg_cache.items())[-4:]
                self._jpeg_cache = dict(items)

        # Frees unused CUDA allocator blocks without unloading the model weights.
        if (
            self.release_cuda_cache
            and self._inference_device.startswith("cuda")
            and torch is not None
            and torch.cuda.is_available()
        ):
            torch.cuda.empty_cache()


__all__ = ["BarcodeStream"]
