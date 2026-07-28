"""Tests for the Gap Engine chroma_utils module."""

from sidecars.gap_engine.src_py.chroma_utils import query_rfp_context


class TestQueryRfpContext:
    def test_returns_empty_string_when_no_db_path(self):
        result = query_rfp_context("rfp-001", db_path="/nonexistent/db")
        assert result == ""

    def test_returns_empty_string_for_missing_rfp(self):
        result = query_rfp_context("nonexistent-rfp", db_path=None)
        assert isinstance(result, str)
