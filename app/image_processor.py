"""
image_processor.py

Two responsibilities, kept strictly separate:
  1. validate_quality()  -> QualityReport (never mutates the image)
  2. enhance_image()      -> corrected image bytes (only called if validation passed)

Both work on OpenCV BGR numpy arrays; conversion from raw upload bytes
happens in `bytes_to_image` / `image_to_bytes` at the edges.
"""
from __future__ import annotations

import logging

import cv2
import numpy as np

from app.config import get_settings
from app.schemas import QualityReport

logger = logging.getLogger(__name__)
settings = get_settings()


# ---------------------------------------------------------------------------
# Conversion helpers
# ---------------------------------------------------------------------------

def bytes_to_image(data: bytes) -> np.ndarray:
    if not data:
        raise ValueError("Image data is empty")
    arr = np.frombuffer(data, dtype=np.uint8)
    image = cv2.imdecode(arr, cv2.IMREAD_COLOR)
    if image is None:
        raise ValueError("Could not decode image — file may be corrupt or an unsupported format")
    return image


def image_to_bytes(image: np.ndarray, ext: str = ".png") -> bytes:
    success, buf = cv2.imencode(ext, image)
    if not success:
        raise ValueError("Failed to encode image")
    return buf.tobytes()


# ---------------------------------------------------------------------------
# Quality metrics
# ---------------------------------------------------------------------------

def _blur_score(gray: np.ndarray) -> float:
    """Laplacian variance — lower means blurrier."""
    return float(cv2.Laplacian(gray, cv2.CV_64F).var())


def _brightness_score(gray: np.ndarray) -> float:
    return float(np.mean(gray))


def _contrast_score(gray: np.ndarray) -> float:
    return float(np.std(gray))


def _noise_score(gray: np.ndarray) -> float:
    """Estimate high-frequency noise using the median absolute Laplacian."""
    laplacian = cv2.Laplacian(gray, cv2.CV_64F)
    return float(np.median(np.abs(laplacian)))


def _skew_angle(gray: np.ndarray) -> float:
    """
    Estimates document skew via minAreaRect over thresholded foreground
    pixels. Returns degrees; 0 = perfectly upright.
    """
    thresh = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV | cv2.THRESH_OTSU)[1]
    coords = np.column_stack(np.where(thresh > 0))
    if coords.shape[0] < 10:
        return 0.0
    angle = cv2.minAreaRect(coords)[-1]
    # cv2.minAreaRect returns angle in [-90, 0); normalize to [-45, 45]
    if angle < -45:
        angle = -(90 + angle)
    else:
        angle = -angle
    return float(angle)


def validate_quality(image: np.ndarray) -> QualityReport:
    if image.ndim != 3 or image.shape[2] != 3:
        raise ValueError("Expected a color BGR image")
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

    blur = _blur_score(gray)
    brightness = _brightness_score(gray)
    contrast = _contrast_score(gray)
    noise = _noise_score(gray)
    height, width = gray.shape
    skew = _skew_angle(gray)
    is_skewed = abs(skew) > settings.skew_angle_threshold
    resolution_passed = True

    reasons = []
    if blur < settings.blur_threshold:
        reasons.append(f"blurry (score={blur:.1f} < {settings.blur_threshold})")
    if brightness < settings.brightness_low:
        reasons.append(f"too dark (mean={brightness:.1f})")
    if brightness > settings.brightness_high:
        reasons.append(f"washed out / overexposed (mean={brightness:.1f})")
    if is_skewed:
        reasons.append(f"skewed (angle={skew:.1f} deg)")
    if contrast < settings.min_contrast:
        reasons.append(f"low contrast (score={contrast:.1f} < {settings.min_contrast})")
    if noise > settings.max_noise_score:
        reasons.append(f"excessive noise (score={noise:.1f} > {settings.max_noise_score})")

    return QualityReport(
        blur_score=blur,
        brightness_score=brightness,
        contrast_score=contrast,
        width=width,
        height=height,
        noise_score=noise,
        resolution_passed=resolution_passed,
        skew_angle=skew,
        is_skewed=is_skewed,
        passed=len(reasons) == 0,
        failure_reasons=reasons,
    )


# ---------------------------------------------------------------------------
# Enhancement pipeline (only run on images that passed validation)
# ---------------------------------------------------------------------------

def _order_points(pts: np.ndarray) -> np.ndarray:
    rect = np.zeros((4, 2), dtype="float32")
    s = pts.sum(axis=1)
    rect[0] = pts[np.argmin(s)]   # top-left
    rect[2] = pts[np.argmax(s)]   # bottom-right
    diff = np.diff(pts, axis=1)
    rect[1] = pts[np.argmin(diff)]  # top-right
    rect[3] = pts[np.argmax(diff)]  # bottom-left
    return rect


def perspective_correction(image: np.ndarray) -> np.ndarray:
    """
    Finds the largest 4-point contour (assumed to be the answer sheet
    page) and warps it to a flat top-down view. Falls back to the
    original image if no clean quadrilateral is found — a hackathon-safe
    default rather than raising and failing the whole pipeline.
    """
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    blurred = cv2.GaussianBlur(gray, (5, 5), 0)
    edged = cv2.Canny(blurred, 50, 150)
    edged = cv2.dilate(edged, None, iterations=2)

    contours, _ = cv2.findContours(edged, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not contours:
        return image

    largest = max(contours, key=cv2.contourArea)
    if cv2.contourArea(largest) < 0.2 * image.shape[0] * image.shape[1]:
        # Contour too small to trust as "the page" — skip warp.
        return image

    peri = cv2.arcLength(largest, True)
    approx = cv2.approxPolyDP(largest, 0.02 * peri, True)
    if len(approx) != 4:
        return image

    pts = approx.reshape(4, 2).astype("float32")
    rect = _order_points(pts)
    (tl, tr, br, bl) = rect

    width = int(max(np.linalg.norm(br - bl), np.linalg.norm(tr - tl)))
    height = int(max(np.linalg.norm(tr - br), np.linalg.norm(tl - bl)))
    if width == 0 or height == 0:
        return image

    dst = np.array([[0, 0], [width - 1, 0], [width - 1, height - 1], [0, height - 1]], dtype="float32")
    matrix = cv2.getPerspectiveTransform(rect, dst)
    return cv2.warpPerspective(image, matrix, (width, height))


def deskew(image: np.ndarray) -> np.ndarray:
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    angle = _skew_angle(gray)
    if abs(angle) < 0.5:
        return image  # not worth rotating
    (h, w) = image.shape[:2]
    center = (w // 2, h // 2)
    matrix = cv2.getRotationMatrix2D(center, angle, 1.0)
    return cv2.warpAffine(
        image, matrix, (w, h), flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_REPLICATE
    )


def denoise(image: np.ndarray) -> np.ndarray:
    return cv2.fastNlMeansDenoisingColored(image, None, h=7, hColor=7,
                                            templateWindowSize=7, searchWindowSize=21)


def apply_clahe(image: np.ndarray) -> np.ndarray:
    lab = cv2.cvtColor(image, cv2.COLOR_BGR2LAB)
    l, a, b = cv2.split(lab)
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    l = clahe.apply(l)
    merged = cv2.merge((l, a, b))
    return cv2.cvtColor(merged, cv2.COLOR_LAB2BGR)


def enhance_image(image: np.ndarray) -> np.ndarray:
    """Full enhancement chain, in order: perspective -> deskew -> denoise -> CLAHE."""
    step = perspective_correction(image)
    step = deskew(step)
    step = denoise(step)
    step = apply_clahe(step)
    return step
