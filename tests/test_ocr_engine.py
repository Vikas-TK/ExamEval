from unittest.mock import patch, MagicMock
import pytest
from app.ocr_engine import extract_page, _safe_json_parse, _fallback_page, OCRPage
from app.core.config import get_settings

settings = get_settings()


def test_safe_json_parse_handles_fences():
    assert _safe_json_parse('```json\n{"confidence": 0.8}\n```') == {"confidence": 0.8}
    assert _safe_json_parse('[1, 2]') is None
    assert _safe_json_parse('not json') is None


def test_got_ocr_success():
    mock_got_page = OCRPage(
        page_number=1,
        transcript="13. Reservation System",
        structure_map={"engine": "got-ocr-2.0"},
        confidence=0.9,
        visual_elements=[],
    )
    with patch("app.ocr_engine.settings.got_ocr_enabled", True):
        with patch("app.ocr_engine._extract_got_page", return_value=mock_got_page):
            res = extract_page(b"fake-image-bytes", 1)
            assert res.transcript == "13. Reservation System"
            assert res.structure_map.get("engine") == "got-ocr-2.0"


def test_got_ocr_failure_falls_back_to_qwen():
    mock_qwen_page = OCRPage(
        page_number=1,
        transcript="Qwen extracted text",
        structure_map={"engine": "qwen2.5-vl"},
        confidence=0.85,
        visual_elements=[],
    )
    with patch("app.ocr_engine.settings.got_ocr_enabled", True):
        with patch("app.ocr_engine._extract_got_page", side_effect=RuntimeError("CUDA Out of Memory")):
            with patch("app.ocr_engine._extract_qwen_page", return_value=mock_qwen_page):
                res = extract_page(b"fake-image-bytes", 1)
                assert res.transcript == "Qwen extracted text"


def test_got_ocr_disabled_skips_directly_to_qwen():
    mock_qwen_page = OCRPage(
        page_number=1,
        transcript="Direct Qwen text",
        structure_map={"engine": "qwen2.5-vl"},
        confidence=0.85,
        visual_elements=[],
    )
    with patch("app.ocr_engine.settings.got_ocr_enabled", False):
        with patch("app.ocr_engine._extract_got_page") as mock_got:
            with patch("app.ocr_engine._extract_qwen_page", return_value=mock_qwen_page):
                res = extract_page(b"fake-image-bytes", 1)
                mock_got.assert_not_called()
                assert res.transcript == "Direct Qwen text"


def test_offline_fallback_chain_returns_ocr_page():
    page, reason = _fallback_page(b"fake-image-bytes", 1, "test_reason")
    assert isinstance(page, OCRPage)
    assert page.page_number == 1
