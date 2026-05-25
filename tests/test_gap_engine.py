"""Tests for the Gap Engine module."""

import json
import os
import sys
import pytest

# The gap engine lives at sidecars/gap-engine/src_py/gap_engine.py
# Python can't import from dirs with hyphens, so we add the path directly
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "sidecars", "gap-engine", "src_py"))

import gap_engine as _ge


class TestAnalyzeGaps:
    """Unit tests for analyze_gaps."""

    def test_returns_list(self):
        result = _ge.analyze_gaps("test-rfp-001")
        assert isinstance(result, list)

    def test_returns_expected_fields(self):
        result = _ge.analyze_gaps("test-rfp-001")
        for gap in result:
            assert "area" in gap
            assert "description" in gap

    def test_returns_non_empty(self):
        result = _ge.analyze_gaps("rfp-123")
        assert len(result) > 0

    def test_known_gaps(self):
        result = _ge.analyze_gaps("rfp-abc")
        areas = [g["area"] for g in result]
        assert "Security" in areas
        assert "Compliance" in areas

    def test_stdout_event(self, capsys):
        _ge.analyze_gaps("rfp-stdout-test")
        captured = capsys.readouterr()
        event = json.loads(captured.out.strip())
        assert event["event"] == "gap_report_generated"
        assert event["data"]["rfpId"] == "rfp-stdout-test"
