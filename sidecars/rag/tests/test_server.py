"""Tests for the RAG server module."""

from sidecars.rag.src_py.server import _pick_best_model


class TestPickBestModel:
    """Tests for the _pick_best_model helper."""

    def test_gemma3_preferred(self):
        models = ["llama3.1:8b", "gemma3:4b", "mistral"]
        result = _pick_best_model(models)
        assert result == "gemma3:4b"

    def test_gemma_preferred_over_mistral(self):
        models = ["mistral", "gemma:2b"]
        result = _pick_best_model(models)
        assert result == "gemma:2b"

    def test_fallback_to_first(self):
        models = ["custom-model", "another-model"]
        result = _pick_best_model(models)
        assert result == "custom-model"

    def test_partial_match(self):
        models = ["qwen3:8b"]
        result = _pick_best_model(models)
        assert result == "qwen3:8b"

    def test_empty_list_returns_default(self):
        result = _pick_best_model([])
        assert result == "gemma3:4b"
