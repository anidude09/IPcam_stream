import json
import threading
import time
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

import cv2
import numpy as np

from .config import LiveConfig, PipelineConfig, StreamConfig
from .engine import YoloBarcodeEngine


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class _SessionLogger:
    def __init__(self, interval_gap_close_sec: float):
        self.session_start_iso = _utc_now_iso()
        self.interval_gap_close_sec = interval_gap_close_sec
        self.active: Dict[str, Dict[str, Any]] = {}
        self.closed_intervals: list[Dict[str, Any]] = []
        self.total_frames_processed = 0
        self.total_frames_with_detections = 0

    def observe(self, frame_idx: int, frame_ts: float, detections: list[Dict[str, Any]]):
        self.total_frames_processed += 1
        if detections:
            self.total_frames_with_detections += 1

        seen_ids = set()
        for det in detections:
            barcode_id = str(det.get("extracted_id", "")).strip()
            if not barcode_id:
                continue
            seen_ids.add(barcode_id)
            if barcode_id not in self.active:
                self.active[barcode_id] = {
                    "barcode_id": barcode_id,
                    "start_frame_idx": frame_idx,
                    "end_frame_idx": frame_idx,
                    "start_ts_unix": frame_ts,
                    "end_ts_unix": frame_ts,
                    "count": 1,
                    "max_confidence": float(det.get("confidence", 0.0)),
                    "last_bbox": det.get("bbox"),
                    "last_raw": det.get("barcode_text"),
                    "last_format": det.get("barcode_format"),
                    "last_method": det.get("decode_method"),
                }
            else:
                cur = self.active[barcode_id]
                cur["end_frame_idx"] = frame_idx
                cur["end_ts_unix"] = frame_ts
                cur["count"] += 1
                cur["max_confidence"] = max(cur["max_confidence"], float(det.get("confidence", 0.0)))
                cur["last_bbox"] = det.get("bbox")
                cur["last_raw"] = det.get("barcode_text")
                cur["last_format"] = det.get("barcode_format")
                cur["last_method"] = det.get("decode_method")

        # Close stale active intervals if no recent hit.
        stale_ids = []
        for barcode_id, interval in self.active.items():
            if barcode_id in seen_ids:
                continue
            if frame_ts - float(interval["end_ts_unix"]) >= self.interval_gap_close_sec:
                stale_ids.append(barcode_id)
        for barcode_id in stale_ids:
            self._close_interval(barcode_id)

    def _close_interval(self, barcode_id: str):
        interval = self.active.pop(barcode_id, None)
        if interval is None:
            return
        duration = float(interval["end_ts_unix"]) - float(interval["start_ts_unix"])
        interval["duration_sec"] = max(0.0, duration)
        self.closed_intervals.append(interval)

    def finalize(self, output_json_path: Path, pipeline_cfg: PipelineConfig, stream_cfg: StreamConfig, live_cfg: LiveConfig):
        # Close all remaining active intervals at shutdown.
        for barcode_id in list(self.active.keys()):
            self._close_interval(barcode_id)

        session_end_iso = _utc_now_iso()
        payload = {
            "session_start_utc": self.session_start_iso,
            "session_end_utc": session_end_iso,
            "summary": {
                "frames_processed": self.total_frames_processed,
                "frames_with_detections": self.total_frames_with_detections,
                "unique_barcodes": sorted({i["barcode_id"] for i in self.closed_intervals}),
                "interval_count": len(self.closed_intervals),
            },
            "configs": {
                "pipeline": asdict(pipeline_cfg),
                "stream": asdict(stream_cfg),
                "live": asdict(live_cfg),
            },
            "detection_intervals": self.closed_intervals,
        }
        output_json_path.parent.mkdir(parents=True, exist_ok=True)
        output_json_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


class _LatestFrameGrabber:
    def __init__(self, source: str, reconnect_backoff_sec: float):
        self.source = source
        self.reconnect_backoff_sec = reconnect_backoff_sec
        self._stop_event = threading.Event()
        self._lock = threading.Lock()
        self._latest: Optional[Tuple[int, float, np.ndarray]] = None
        self._frame_idx = 0
        self._fps = 0.0
        self._thread = threading.Thread(target=self._run, daemon=True)

    def start(self):
        self._thread.start()

    def stop(self):
        self._stop_event.set()
        self._thread.join(timeout=2.0)

    @property
    def fps(self) -> float:
        return self._fps

    def get_latest(self) -> Optional[Tuple[int, float, np.ndarray]]:
        with self._lock:
            return self._latest

    def _open_capture(self):
        cap = cv2.VideoCapture(self.source)
        if cap.isOpened():
            cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
            self._fps = cap.get(cv2.CAP_PROP_FPS)
            return cap
        return None

    def _run(self):
        cap = None
        while not self._stop_event.is_set():
            if cap is None:
                cap = self._open_capture()
                if cap is None:
                    time.sleep(self.reconnect_backoff_sec)
                    continue

            ok, frame = cap.read()
            if not ok:
                cap.release()
                cap = None
                time.sleep(self.reconnect_backoff_sec)
                continue

            ts = time.time()
            idx = self._frame_idx
            self._frame_idx += 1
            with self._lock:
                self._latest = (idx, ts, frame)

        if cap is not None:
            cap.release()


def run_live_rtsp_session(
    rtsp_url: str,
    pipeline_cfg: PipelineConfig,
    stream_cfg: StreamConfig,
    live_cfg: LiveConfig,
    max_frames: int | None = None,
):
    output_dir = Path(live_cfg.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    engine = YoloBarcodeEngine(pipeline_cfg=pipeline_cfg, stream_cfg=stream_cfg)
    logger = _SessionLogger(interval_gap_close_sec=live_cfg.interval_gap_close_sec)
    grabber = _LatestFrameGrabber(rtsp_url, reconnect_backoff_sec=live_cfg.reconnect_backoff_sec)

    print(f"Loading YOLO model: {pipeline_cfg.model_path}")
    print("Model loaded successfully!")
    print(f"Using inference device: {engine.pipeline.device}")
    print(f"RTSP source: {rtsp_url}")

    writer = None
    processed_frame_count = 0
    last_seen_idx = -1
    session_basename = f"rtsp_session_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    out_video_path = output_dir / f"{session_basename}.mp4"
    out_json_path = output_dir / f"{session_basename}.json"

    grabber.start()
    try:
        while True:
            item = grabber.get_latest()
            if item is None:
                time.sleep(live_cfg.poll_sleep_sec)
                continue

            frame_idx, frame_ts, frame = item
            if frame_idx <= last_seen_idx:
                time.sleep(live_cfg.poll_sleep_sec)
                continue
            last_seen_idx = frame_idx

            vis, detections = engine.process_stream_frame(frame)
            logger.observe(frame_idx=frame_idx, frame_ts=frame_ts, detections=detections)
            processed_frame_count += 1

            if writer is None and live_cfg.save_annotated_video:
                h, w = vis.shape[:2]
                fps = grabber.fps if grabber.fps and grabber.fps > 0 else live_cfg.source_fps_fallback
                writer = cv2.VideoWriter(
                    str(out_video_path),
                    cv2.VideoWriter_fourcc(*"mp4v"),
                    fps,
                    (w, h),
                )

            if writer is not None:
                writer.write(vis)

            if live_cfg.display_live:
                disp = vis
                if live_cfg.display_scale != 1.0:
                    disp = cv2.resize(
                        vis,
                        None,
                        fx=live_cfg.display_scale,
                        fy=live_cfg.display_scale,
                        interpolation=cv2.INTER_AREA,
                    )
                cv2.imshow(live_cfg.display_window_name, disp)
                if cv2.waitKey(1) & 0xFF == ord("q"):
                    print("Stopped by user (q).")
                    break

            if max_frames is not None and processed_frame_count >= max_frames:
                break
    except KeyboardInterrupt:
        print("Stopped by keyboard interrupt.")
    finally:
        grabber.stop()
        if writer is not None:
            writer.release()
            print(f"Saved annotated video: {out_video_path}")
        if live_cfg.display_live:
            cv2.destroyAllWindows()
        if live_cfg.save_session_json:
            logger.finalize(
                output_json_path=out_json_path,
                pipeline_cfg=pipeline_cfg,
                stream_cfg=stream_cfg,
                live_cfg=live_cfg,
            )
            print(f"Saved session JSON: {out_json_path}")
