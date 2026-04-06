from pathlib import Path
from typing import Dict, List

import cv2

from .config import LiveConfig, PipelineConfig, StreamConfig
from .engine import YoloBarcodeEngine
from .live import run_live_rtsp_session


def collect_images(input_path: str) -> List[Path]:
    p = Path(input_path)
    if p.is_file():
        return [p]
    if p.is_dir():
        return sorted(
            list(p.glob("*.jpg"))
            + list(p.glob("*.jpeg"))
            + list(p.glob("*.png"))
            + list(p.glob("*.JPG"))
            + list(p.glob("*.JPEG"))
        )
    return []


def run_images(input_path: str, pipeline_cfg: PipelineConfig) -> Dict[str, List[dict]]:
    engine = YoloBarcodeEngine(pipeline_cfg=pipeline_cfg)
    image_paths = collect_images(input_path)
    if not image_paths:
        print(f"No images found in '{input_path}'")
        return {}

    output_dir = Path(pipeline_cfg.output_dir)
    output_dir.mkdir(exist_ok=True)

    print(f"Loading YOLO model: {pipeline_cfg.model_path}")
    print("Model loaded successfully!")
    print(f"Using inference device: {engine.pipeline.device}")
    print(f"\nFound {len(image_paths)} image(s) to process")
    print("=" * 60)

    all_results: Dict[str, List[dict]] = {}
    for i, img_path in enumerate(image_paths, 1):
        print(f"\n[{i}/{len(image_paths)}]")
        print("\n" + "=" * 60)
        print(f"Processing: {img_path}")
        img = cv2.imread(str(img_path))
        if img is None:
            print("  ERROR: Could not read image")
            all_results[str(img_path)] = []
            continue
        h, w = img.shape[:2]
        print(f"  Image size: {w} x {h} px")
        vis, results = engine.process_frame(img, frame_tag=img_path.stem)
        print(f"  Detections decoded: {len(results)}")
        for j, r in enumerate(results, 1):
            x1, y1, x2, y2 = r["bbox"]
            print(
                f"    Det {j}: id='{r['extracted_id']}', raw='{r['barcode_text']}', "
                f"format={r['barcode_format']}, conf={r['confidence']:.2f}, bbox=({x1},{y1},{x2},{y2})"
            )
        out_img = output_dir / f"{img_path.stem}_detection.jpg"
        cv2.imwrite(str(out_img), vis)
        print(f"  Saved visualization to: {out_img}")

        if pipeline_cfg.save_metadata_txt:
            txt_path = output_dir / f"{img_path.stem}_detections.txt"
            with txt_path.open("w", encoding="utf-8") as f:
                f.write("image,bbox_x1,bbox_y1,bbox_x2,bbox_y2,confidence,barcode_id,barcode_raw,barcode_format,decode_method\n")
                for r in results:
                    x1, y1, x2, y2 = r["bbox"]
                    f.write(
                        f"{img_path.name},{x1},{y1},{x2},{y2},{r['confidence']:.4f},"
                        f"{r.get('extracted_id','')},{r.get('barcode_text','')},"
                        f"{r.get('barcode_format','')},{r.get('decode_method','')}\n"
                    )
            print(f"  Saved metadata to: {txt_path}")

        all_results[str(img_path)] = results

    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    for img_path, results in all_results.items():
        if not results:
            print(f"  {Path(img_path).name}: NO BARCODES DETECTED/DECODED")
        else:
            ids = [r["extracted_id"] for r in results]
            raws = [r["barcode_text"] for r in results]
            print(f"  {Path(img_path).name}: {len(results)} detection(s) -> ids={ids}, raw={raws}")
    return all_results


def build_stream_engine(pipeline_cfg: PipelineConfig, stream_cfg: StreamConfig) -> YoloBarcodeEngine:
    return YoloBarcodeEngine(pipeline_cfg=pipeline_cfg, stream_cfg=stream_cfg)


def run_from_settings() -> Dict[str, List[dict]]:
    from .settings import INPUT_SOURCE, PIPELINE

    return run_images(INPUT_SOURCE, PIPELINE)


def run_live_from_settings(max_frames: int | None = None):
    from .settings import LIVE, PIPELINE, RTSP_URL, STREAM

    return run_live_rtsp_session(
        rtsp_url=RTSP_URL,
        pipeline_cfg=PIPELINE,
        stream_cfg=STREAM,
        live_cfg=LIVE,
        max_frames=max_frames,
    )
