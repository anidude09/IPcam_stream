from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import cv2
import numpy as np
import zxingcpp
from pyzbar import pyzbar
from ultralytics import YOLO
try:
    import torch
except Exception:  # pragma: no cover - defensive fallback
    torch = None


@dataclass
class CoreConfig:
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
    output_dir: str = "package_output_barcode"


def _is_code128_format(barcode_format: Any) -> bool:
    normalized = "".join(ch for ch in str(barcode_format).upper() if ch.isalnum())
    return "CODE128" in normalized


def _normalize_text(decoded_text: Any) -> str:
    if decoded_text is None:
        return ""
    cleaned = str(decoded_text).strip().strip("*")
    return "".join(ch for ch in cleaned if ch.isalnum())


def _extract_numeric_id(decoded_text: Any) -> Dict[str, Any]:
    normalized = _normalize_text(decoded_text)
    digits = "".join(ch for ch in normalized if ch.isdigit())
    if not digits:
        return {"ok": False, "extracted_id": None, "normalized_text": normalized}
    extracted = digits.zfill(2)[:2] if len(digits) == 1 else digits[:2]
    return {"ok": True, "extracted_id": extracted, "normalized_text": normalized}


def _score_candidate(text: str, barcode_format: Any) -> int:
    normalized = _normalize_text(text)
    digits = "".join(ch for ch in normalized if ch.isdigit())
    if not digits:
        return -1
    score = 0
    if _is_code128_format(barcode_format):
        score += 100
    if len(digits) == 2:
        score += 60
    elif len(digits) == 1:
        score += 30
    elif len(digits) <= 4:
        score += 10
    else:
        score -= 20
    score += min(20, int(20 * (len(digits) / max(len(normalized), 1))))
    return score


def _preprocess_gray(gray: np.ndarray, method: str) -> np.ndarray:
    if method == "original":
        return gray
    if method == "clahe":
        return cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8, 8)).apply(gray)
    if method == "clahe_sharp":
        clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8, 8)).apply(gray)
        kernel = np.array([[0, -1, 0], [-1, 5, -1], [0, -1, 0]], dtype=np.float32)
        return cv2.filter2D(clahe, -1, kernel)
    if method == "otsu":
        blurred = cv2.GaussianBlur(gray, (5, 5), 0)
        _, out = cv2.threshold(blurred, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        return out
    return gray


def _build_decode_variants(crop: np.ndarray, fast_decode: bool) -> List[Tuple[str, np.ndarray]]:
    gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY) if len(crop.shape) == 3 else crop
    methods = ["original", "otsu"] if fast_decode else ["original", "clahe", "clahe_sharp", "otsu"]
    variants: List[Tuple[str, np.ndarray]] = []
    for method in methods:
        base = _preprocess_gray(gray, method)
        variants.append((method, base))
        variants.append((f"{method}_x2", cv2.resize(base, None, fx=2.0, fy=2.0, interpolation=cv2.INTER_CUBIC)))
    variants.append(("rot90", cv2.rotate(gray, cv2.ROTATE_90_CLOCKWISE)))
    variants.append(("rot270", cv2.rotate(gray, cv2.ROTATE_90_COUNTERCLOCKWISE)))
    return variants


def _order_points(pts: np.ndarray) -> np.ndarray:
    rect = np.zeros((4, 2), dtype=np.float32)
    s = pts.sum(axis=1)
    rect[0] = pts[np.argmin(s)]
    rect[2] = pts[np.argmax(s)]
    d = np.diff(pts, axis=1)
    rect[1] = pts[np.argmin(d)]
    rect[3] = pts[np.argmax(d)]
    return rect


def _warp_min_rect(img: np.ndarray, min_rect: Any) -> Optional[np.ndarray]:
    box = cv2.boxPoints(min_rect).astype(np.float32)
    tl, tr, br, bl = _order_points(box)
    max_w = int(max(np.linalg.norm(br - bl), np.linalg.norm(tr - tl)))
    max_h = int(max(np.linalg.norm(tr - br), np.linalg.norm(tl - bl)))
    if max_w < 20 or max_h < 20:
        return None
    dst = np.array([[0, 0], [max_w - 1, 0], [max_w - 1, max_h - 1], [0, max_h - 1]], dtype=np.float32)
    M = cv2.getPerspectiveTransform(np.array([tl, tr, br, bl], dtype=np.float32), dst)
    warped = cv2.warpPerspective(img, M, (max_w, max_h))
    if warped.shape[0] > warped.shape[1]:
        warped = cv2.rotate(warped, cv2.ROTATE_90_CLOCKWISE)
    return warped


def _refine_roi_candidates(crop: np.ndarray, enabled: bool) -> List[Tuple[str, np.ndarray]]:
    out = [("original_crop", crop)]
    if not enabled:
        return out
    gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY) if len(crop.shape) == 3 else crop
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8)).apply(gray)
    gx = cv2.Sobel(clahe, cv2.CV_32F, 1, 0, ksize=-1)
    gy = cv2.Sobel(clahe, cv2.CV_32F, 0, 1, ksize=-1)
    grad = cv2.convertScaleAbs(cv2.subtract(gx, gy))
    blur = cv2.GaussianBlur(grad, (9, 9), 0)
    _, bw = cv2.threshold(blur, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    bw = cv2.morphologyEx(bw, cv2.MORPH_CLOSE, cv2.getStructuringElement(cv2.MORPH_RECT, (31, 11)))
    bw = cv2.erode(bw, None, iterations=2)
    bw = cv2.dilate(bw, None, iterations=2)
    contours, _ = cv2.findContours(bw, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not contours:
        return out
    area_total = crop.shape[0] * crop.shape[1]
    for i, contour in enumerate(sorted(contours, key=cv2.contourArea, reverse=True)[:3]):
        if cv2.contourArea(contour) < 0.02 * area_total:
            continue
        min_rect = cv2.minAreaRect(contour)
        wr, hr = min_rect[1]
        if min(wr, hr) < 10:
            continue
        if max(wr, hr) / max(min(wr, hr), 1e-6) < 1.2:
            continue
        warped = _warp_min_rect(crop, min_rect)
        if warped is not None:
            out.append((f"roi_rectified_{i+1}", warped))
    return out


class BarcodeCorePipeline:
    def __init__(self, model_path: str, config: Optional[CoreConfig] = None):
        self.config = config or CoreConfig()
        self.model = YOLO(model_path)
        self.device = self._resolve_device(self.config.device)
        self.output_dir = Path(self.config.output_dir)
        self.crops_dir = self.output_dir / "crops"
        if self.config.save_output:
            self.output_dir.mkdir(exist_ok=True)
            self.crops_dir.mkdir(exist_ok=True)

    @staticmethod
    def _resolve_device(requested_device: str) -> str:
        if requested_device != "auto":
            return requested_device
        if torch is not None and torch.cuda.is_available():
            return "cuda:0"
        if (
            torch is not None
            and hasattr(torch.backends, "mps")
            and torch.backends.mps.is_available()
        ):
            return "mps"
        return "cpu"

    def detect_regions(self, frame: np.ndarray) -> List[Dict[str, Any]]:
        result = self.model(
            frame,
            verbose=False,
            conf=self.config.conf_threshold,
            imgsz=self.config.imgsz,
            device=self.device,
        )[0]
        detections: List[Dict[str, Any]] = []
        for box in result.boxes:
            x1, y1, x2, y2 = box.xyxy[0].cpu().numpy().astype(int)
            w, h = x2 - x1, y2 - y1
            if w < self.config.min_box_size or h < self.config.min_box_size:
                continue
            detections.append(
                {
                    "bbox": (x1, y1, x2, y2),
                    "confidence": float(box.conf[0]),
                    "class": result.names[int(box.cls[0])] if hasattr(result, "names") else "barcode",
                    "width": w,
                    "height": h,
                }
            )
        return detections

    def _decode_crop(self, crop: np.ndarray, debug_dir: Optional[Path]) -> Optional[Dict[str, Any]]:
        candidates: List[Dict[str, Any]] = []
        roi_candidates = _refine_roi_candidates(crop, self.config.use_roi_refine)
        variant_map: Dict[str, np.ndarray] = {}
        if debug_dir is not None and self.config.save_preprocess_steps:
            debug_dir.mkdir(parents=True, exist_ok=True)
            cv2.imwrite(str(debug_dir / "00_before_original_crop.jpg"), crop)

        for roi_name, roi in roi_candidates:
            variants = _build_decode_variants(roi, self.config.fast_decode)
            for var_name, variant_img in variants:
                key = f"{roi_name}__{var_name}"
                variant_map[key] = variant_img
                if debug_dir is not None and self.config.save_preprocess_steps:
                    cv2.imwrite(str(debug_dir / f"10_{key}.jpg"), variant_img)

                try:
                    for r in zxingcpp.read_barcodes(variant_img):
                        score = _score_candidate(r.text, r.format)
                        if score >= 0:
                            candidates.append(
                                {
                                    "text": r.text,
                                    "format": r.format,
                                    "method": f"zxingcpp_{var_name}",
                                    "variant": key,
                                    "score": score,
                                }
                            )
                except Exception:
                    pass

                if self.config.fast_decode and any(_is_code128_format(c["format"]) for c in candidates):
                    continue
                try:
                    for r in pyzbar.decode(variant_img):
                        text = r.data.decode("utf-8")
                        score = _score_candidate(text, r.type)
                        if score >= 0:
                            candidates.append(
                                {
                                    "text": text,
                                    "format": r.type,
                                    "method": f"pyzbar_{var_name}",
                                    "variant": key,
                                    "score": score,
                                }
                            )
                except Exception:
                    pass

        if not candidates:
            return None
        candidates.sort(key=lambda x: x["score"], reverse=True)
        best = candidates[0]
        extracted = _extract_numeric_id(best["text"])
        if not extracted["ok"]:
            return None
        if debug_dir is not None and self.config.save_preprocess_steps and best["variant"] in variant_map:
            cv2.imwrite(str(debug_dir / f"20_used_variant_{best['variant']}.jpg"), variant_map[best["variant"]])
        best["extracted_id"] = extracted["extracted_id"]
        best["normalized_text"] = extracted["normalized_text"]
        return best

    def _decode_crop_light_retry(self, crop: np.ndarray) -> Optional[Dict[str, Any]]:
        """
        Lightweight fallback decode used only when primary decode fails.
        Avoids ROI refinement and runs a tiny variant set to keep it fast.
        """
        gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY) if len(crop.shape) == 3 else crop
        variants = [
            ("retry_original", gray),
            ("retry_original_x2", cv2.resize(gray, None, fx=2.0, fy=2.0, interpolation=cv2.INTER_CUBIC)),
            ("retry_otsu", _preprocess_gray(gray, "otsu")),
        ]
        candidates: List[Dict[str, Any]] = []
        for method_name, variant_img in variants:
            try:
                for r in zxingcpp.read_barcodes(variant_img):
                    score = _score_candidate(r.text, r.format)
                    if score >= 0:
                        candidates.append(
                            {
                                "text": r.text,
                                "format": r.format,
                                "method": f"zxingcpp_{method_name}",
                                "variant": method_name,
                                "score": score,
                            }
                        )
            except Exception:
                pass

            # Keep pyzbar as fallback in retry path as well.
            if any(_is_code128_format(c["format"]) for c in candidates):
                continue
            try:
                for r in pyzbar.decode(variant_img):
                    text = r.data.decode("utf-8")
                    score = _score_candidate(text, r.type)
                    if score >= 0:
                        candidates.append(
                            {
                                "text": text,
                                "format": r.type,
                                "method": f"pyzbar_{method_name}",
                                "variant": method_name,
                                "score": score,
                            }
                        )
            except Exception:
                pass

        if not candidates:
            return None
        candidates.sort(key=lambda x: x["score"], reverse=True)
        best = candidates[0]
        extracted = _extract_numeric_id(best["text"])
        if not extracted["ok"]:
            return None
        best["extracted_id"] = extracted["extracted_id"]
        best["normalized_text"] = extracted["normalized_text"]
        return best

    def process_frame(self, frame: np.ndarray, frame_tag: Optional[str] = None) -> Tuple[np.ndarray, List[Dict[str, Any]]]:
        detections = self.detect_regions(frame)
        annotated = frame.copy()
        decoded_results: List[Dict[str, Any]] = []

        if not self.config.enable_decode:
            for det in detections:
                x1, y1, x2, y2 = det["bbox"]
                conf = det["confidence"]
                cv2.rectangle(annotated, (x1, y1), (x2, y2), (0, 255, 0), 2)
                cv2.putText(
                    annotated,
                    f"barcode ({conf:.2f})",
                    (x1, y1 - 10),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.7,
                    (0, 255, 0),
                    2,
                )
                decoded_results.append(
                    {
                        "bbox": det["bbox"],
                        "confidence": conf,
                        "class": det["class"],
                        "barcode_text": None,
                        "normalized_text": None,
                        "extracted_id": None,
                        "barcode_format": None,
                        "decode_method": "disabled",
                        "crop_path": None,
                    }
                )
            return annotated, decoded_results

        max_decode = min(len(detections), self.config.max_decode_per_frame)

        for i, det in enumerate(detections[:max_decode]):
            x1, y1, x2, y2 = det["bbox"]
            conf = det["confidence"]
            pad_x = int((x2 - x1) * self.config.pad_ratio_x)
            pad_y = int((y2 - y1) * self.config.pad_ratio_y)
            cx1 = max(0, x1 - pad_x)
            cy1 = max(0, y1 - pad_y)
            cx2 = min(frame.shape[1], x2 + pad_x)
            cy2 = min(frame.shape[0], y2 + pad_y)
            crop = frame[cy1:cy2, cx1:cx2]

            debug_dir = None
            crop_path = None
            if self.config.save_output:
                tag = frame_tag or "frame"
                crop_name = f"{tag}_{det['class']}_{i + 1}_conf{conf:.2f}.jpg"
                crop_path = str(self.crops_dir / crop_name)
                cv2.imwrite(crop_path, crop)
                if self.config.save_preprocess_steps:
                    debug_dir = self.crops_dir / f"{Path(crop_name).stem}_preprocess_steps"

            decoded = self._decode_crop(crop, debug_dir)
            if decoded is None and self.config.retry_on_decode_fail:
                retry_pad_x = int(pad_x * self.config.retry_pad_scale)
                retry_pad_y = int(pad_y * self.config.retry_pad_scale)
                rx1 = max(0, x1 - retry_pad_x)
                ry1 = max(0, y1 - retry_pad_y)
                rx2 = min(frame.shape[1], x2 + retry_pad_x)
                ry2 = min(frame.shape[0], y2 + retry_pad_y)
                retry_crop = frame[ry1:ry2, rx1:rx2]
                decoded = self._decode_crop_light_retry(retry_crop)

            if decoded is None:
                cv2.rectangle(annotated, (x1, y1), (x2, y2), (0, 140, 255), 2)
                continue

            det_result = {
                "bbox": det["bbox"],
                "confidence": conf,
                "class": det["class"],
                "barcode_text": decoded["text"],
                "normalized_text": decoded["normalized_text"],
                "extracted_id": decoded["extracted_id"],
                "barcode_format": decoded["format"],
                "decode_method": decoded["method"],
                "crop_path": crop_path,
            }
            decoded_results.append(det_result)
            cv2.rectangle(annotated, (x1, y1), (x2, y2), (0, 255, 0), 3)
            cv2.putText(
                annotated,
                f"{decoded['extracted_id']} ({conf:.2f})",
                (x1, y1 - 10),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.8,
                (0, 255, 0),
                2,
            )

        return annotated, decoded_results
