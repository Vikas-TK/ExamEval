from app.ocr_engine import _safe_json_parse


def test_safe_json_parse_handles_fences():
    assert _safe_json_parse('```json\n{"confidence": 0.8}\n```') == {"confidence": 0.8}
    assert _safe_json_parse('[1, 2]') is None
    assert _safe_json_parse('not json') is None
