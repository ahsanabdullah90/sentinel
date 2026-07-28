"""Tests for the RAG ingest module."""

import os
import tempfile

from sidecars.rag.src_py.ingest import _chunk_text, _extract_text


class TestChunkText:
    """Tests for the _chunk_text helper."""

    def test_empty_text(self):
        result = _chunk_text("", "rfp-001")
        assert result == []

    def test_single_chunk(self):
        text = "hello world " * 50  # ~600 chars
        result = _chunk_text(text, "rfp-001")
        assert len(result) == 1
        assert result[0]["id"] == "rfp-001-chunk-0"

    def test_multiple_chunks(self):
        text = "word " * 1000  # ~5000 chars
        result = _chunk_text(text, "rfp-002")
        assert len(result) > 1
        assert all(c["id"].startswith("rfp-002-chunk-") for c in result)

    def test_chunk_ids_are_unique(self):
        text = "word " * 2000
        result = _chunk_text(text, "rfp-003")
        ids = [c["id"] for c in result]
        assert len(ids) == len(set(ids))

    def test_chunk_content_non_empty(self):
        text = "word " * 500
        result = _chunk_text(text, "rfp-004")
        for chunk in result:
            assert len(chunk["text"]) > 0


class TestExtractText:
    """Tests for the _extract_text helper."""

    def test_plain_text_file(self):
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".txt", delete=False, encoding="utf-8"
        ) as f:
            f.write("Hello, this is a test document.")
            temp_path = f.name

        try:
            result = _extract_text(temp_path)
            assert "Hello, this is a test document." in result
        finally:
            os.unlink(temp_path)

    def test_nonexistent_file(self):
        result = _extract_text("/nonexistent/file.txt")
        assert "Unparseable file" in result or result == ""

    def test_empty_file(self):
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".txt", delete=False, encoding="utf-8"
        ) as f:
            temp_path = f.name

        try:
            result = _extract_text(temp_path)
            assert isinstance(result, str)
        finally:
            os.unlink(temp_path)
