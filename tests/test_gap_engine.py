"""Tests for the Gap Engine module."""

import pytest
from sidecars.gap_engine.src_py.gap_analyzer import analyze_gaps


class TestAnalyzeGaps:
    """Unit tests for analyze_gaps."""

    def test_returns_list(self):
        result = analyze_gaps("test-rfp-001")
        assert isinstance(result, list)

    def test_returns_expected_fields(self):
        result = analyze_gaps("test-rfp-001")
        for gap in result:
            assert "area" in gap
            assert "description" in gap

    def test_returns_non_empty(self):
        result = analyze_gaps("rfp-123")
        assert len(result) > 0

    def test_known_gaps(self):
        result = analyze_gaps("rfp-abc")
        areas = [g["area"] for g in result]
        assert "Security" in areas
        assert "Compliance" in areas

    def test_fallback_on_missing_db(self):
        result = analyze_gaps("nonexistent-rfp")
        assert len(result) > 0
        assert result[0]["area"] == "Security"
