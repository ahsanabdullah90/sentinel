"""Tests for the Gap Engine ollama_utils module."""

from sidecars.gap_engine.src_py.ollama_utils import (
    _build_prompt,
    _parse_response,
    FALLBACK_GAPS,
)


class TestBuildPrompt:
    def test_includes_context(self):
        prompt = _build_prompt("Some RFP text")
        assert "Some RFP text" in prompt

    def test_truncates_at_12000_chars(self):
        long_text = "x" * 20000
        prompt = _build_prompt(long_text)
        assert len(prompt) < 20000

    def test_contains_keywords(self):
        prompt = _build_prompt("test")
        assert "compliance auditor" in prompt
        assert "JSON array" in prompt


class TestParseResponse:
    def test_plain_json_array(self):
        raw = '[{"area": "Security", "description": "Missing encryption"}]'
        result = _parse_response(raw)
        assert len(result) == 1
        assert result[0]["area"] == "Security"

    def test_fenced_json(self):
        raw = '```json\n[{"area": "Security", "description": "No encryption"}]\n```'
        result = _parse_response(raw)
        assert len(result) == 1
        assert result[0]["area"] == "Security"

    def test_fenced_no_language(self):
        raw = '```\n[{"area": "Compliance", "description": "FedRAMP missing"}]\n```'
        result = _parse_response(raw)
        assert len(result) == 1

    def test_empty_array(self):
        result = _parse_response("[]")
        assert result == []

    def test_invalid_json_returns_empty(self):
        result = _parse_response("not json")
        assert result == []

    def test_non_list_returns_empty(self):
        result = _parse_response('{"key": "value"}')
        assert result == []

    def test_skips_malformed_items(self):
        raw = '[{"area": "Valid", "description": "OK"}, {"area": "Missing desc"}, {}]'
        result = _parse_response(raw)
        assert len(result) == 1
        assert result[0]["area"] == "Valid"

    def test_strips_whitespace_from_values(self):
        raw = '[{"area": "  Security  ", "description": "  Missing  "}]'
        result = _parse_response(raw)
        assert result[0]["area"] == "  Security  "


class TestFallbackGaps:
    def test_is_list(self):
        assert isinstance(FALLBACK_GAPS, list)

    def test_has_expected_keys(self):
        for g in FALLBACK_GAPS:
            assert "area" in g
            assert "description" in g

    def test_contains_security_and_compliance(self):
        areas = [g["area"] for g in FALLBACK_GAPS]
        assert "Security" in areas
        assert "Compliance" in areas
