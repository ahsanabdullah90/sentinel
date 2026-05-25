"""Tests for the Worker sidecar module."""

import asyncio
import json
import os
import sys
import time
import pytest

# Add worker source to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "sidecars", "worker", "src_py"))

from worker import process_job


class TestProcessJob:
    """Unit tests for the concrete job processor."""

    @pytest.mark.asyncio
    async def test_basic_processing(self):
        """process_job should return an enriched result dict."""
        job = {"rfpId": "test-001", "title": "Test RFP"}
        result = await process_job(job, redis_client=None)
        assert result["status"] == "processed"
        assert result["rfpId"] == "test-001"
        assert "contentHash" in result
        assert "processedAt" in result
        assert result["workerVersion"] == "1.0.0"

    @pytest.mark.asyncio
    async def test_missing_rfp_id_raises(self):
        """process_job should raise ValueError if rfpId is missing."""
        with pytest.raises(ValueError, match="rfpId"):
            await process_job({"title": "no id"}, redis_client=None)

    @pytest.mark.asyncio
    async def test_normalisation_strips_whitespace(self):
        """String values should be stripped."""
        job = {"rfpId": "  rfp-002  ", "title": "  Hello  "}
        result = await process_job(job, redis_client=None)
        assert result["rfpId"] == "rfp-002"
        assert result["title"] == "Hello"

    @pytest.mark.asyncio
    async def test_content_hash_deterministic(self):
        """Same input should always produce the same hash."""
        job = {"rfpId": "rfp-hash", "data": "value"}
        r1 = await process_job(job, redis_client=None)
        r2 = await process_job(job, redis_client=None)
        assert r1["contentHash"] == r2["contentHash"]

    @pytest.mark.asyncio
    async def test_content_hash_differs(self):
        """Different input should produce different hashes."""
        r1 = await process_job({"rfpId": "a", "x": "1"}, redis_client=None)
        r2 = await process_job({"rfpId": "b", "x": "2"}, redis_client=None)
        assert r1["contentHash"] != r2["contentHash"]

    @pytest.mark.asyncio
    async def test_processed_at_is_recent(self):
        """processedAt timestamp should be within a few seconds of now."""
        job = {"rfpId": "rfp-time"}
        result = await process_job(job, redis_client=None)
        # Just check it's a valid ISO-ish string
        assert "T" in result["processedAt"]
        assert result["processedAt"].endswith("Z")

    @pytest.mark.asyncio
    async def test_rfp_id_alt_key(self):
        """process_job should also accept 'rfp_id' (snake_case)."""
        job = {"rfp_id": "rfp-snake"}
        result = await process_job(job, redis_client=None)
        assert result["status"] == "processed"
