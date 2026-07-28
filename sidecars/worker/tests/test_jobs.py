"""Tests for the Worker jobs module."""

import pytest
from sidecars.worker.src_py.jobs import (
    normalize_job_data,
    compute_content_hash,
    format_result,
)


class TestNormalizeJobData:
    def test_strips_keys_and_string_values(self):
        data = {"  rfpId  ": "  rfp-001  ", "  title  ": "  Hello  "}
        result = normalize_job_data(data)
        assert result == {"rfpId": "rfp-001", "title": "Hello"}

    def test_preserves_non_string_values(self):
        data = {"rfpId": "test", "count": 42, "active": True}
        result = normalize_job_data(data)
        assert result["count"] == 42
        assert result["active"] is True

    def test_empty_dict(self):
        assert normalize_job_data({}) == {}


class TestComputeContentHash:
    def test_deterministic(self):
        data = {"a": 1, "b": 2}
        h1 = compute_content_hash(data)
        h2 = compute_content_hash(data)
        assert h1 == h2

    def test_differs_for_different_data(self):
        h1 = compute_content_hash({"x": "1"})
        h2 = compute_content_hash({"x": "2"})
        assert h1 != h2

    def test_length(self):
        h = compute_content_hash({"test": "data"})
        assert len(h) == 16

    def test_is_hex(self):
        h = compute_content_hash({"test": "data"})
        int(h, 16)  # raises if not valid hex


class TestFormatResult:
    def test_includes_all_fields(self):
        normalized = {"rfpId": "test-001", "title": "Test"}
        h = "abc123"
        result = format_result(normalized, h)
        assert result["rfpId"] == "test-001"
        assert result["contentHash"] == "abc123"
        assert result["status"] == "processed"
        assert result["workerVersion"] == "1.0.0"
        assert "processedAt" in result

    def test_preserves_extra_keys(self):
        normalized = {"rfpId": "t1", "extra": "value"}
        result = format_result(normalized, "hash1")
        assert result["extra"] == "value"
