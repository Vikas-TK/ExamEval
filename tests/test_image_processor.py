import cv2
import numpy as np

from app.image_processor import bytes_to_image, image_to_bytes, validate_quality


def test_image_round_trip_and_quality_metrics():
    image = np.full((800, 1000, 3), 180, dtype=np.uint8)
    cv2.putText(image, "EXAM", (100, 300), cv2.FONT_HERSHEY_SIMPLEX, 4, (0, 0, 0), 8)
    decoded = bytes_to_image(image_to_bytes(image))
    report = validate_quality(decoded)
    assert report.width == 1000
    assert report.height == 800
    assert report.contrast_score > 0
    assert 0 <= report.noise_score


def test_corrupt_image_is_rejected():
    try:
        bytes_to_image(b"not-an-image")
    except ValueError as exc:
        assert "decode" in str(exc)
    else:
        raise AssertionError("corrupt image was accepted")
