"""Tests for the RAG server module."""

from sidecars.rag.src_py.server import _pick_best_model


class TestPickBestModel:
    """Tests for the _pick_best_model helper."""

    def test_preferred_model_found(self):
        models = ["llama3.1:8b", "mistral", "codellama"]
        result = _pick_best_model(models)
        assert result == "llama3.1:8b"

    def test_gemma_preferred_over_mistral(self):
        models = ["mistral", "gemma:2b"]
        result = _pick_best_model(models)
        assert result == "gemma:2b"

    def test_fallback_to_first(self):
        models = ["custom-model", "another-model"]
        result = _pick_best_model(models)
        assert result == "custom-model"

    def test_partial_match(self):
        models = ["qwen2.5-coder:7b"]
        result = _pick_best_model(models)
        assert result == "qwen2.5-coder:7b"

    def test_empty_list_returns_default(self):
        result = _pick_best_model([])
        assert result == "llama3.1:8b"
