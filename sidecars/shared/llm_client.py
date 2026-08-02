"""Shared LLM Client Module

Provides a provider-agnostic async wrapper for text generation, model
listing, and health checks across two providers:

- **Google Gemini** (Google AI Studio / Generative Language API) — the
  cloud-first default. Uses the ``generativelanguage.googleapis.com`` REST
  API with an API key.
- **Ollama** — local fallback for machines that can run it.

All Sentinel sidecars (hunter, rag, gap_engine) import this module so the
provider choice is centralized. Provider configuration can be supplied via
explicit arguments, JSON-RPC params, or environment variables:

- ``LLM_PROVIDER`` (``google`` | ``ollama``)
- ``GOOGLE_API_KEY``
- ``GOOGLE_LLM_MODEL`` (default ``gemini-2.5-flash``)
- ``OLLAMA_URL`` (default ``http://127.0.0.1:11434``)
- ``OLLAMA_MODEL``
"""

import asyncio
import json
import logging
import os
import urllib.request

logger = logging.getLogger("shared.llm_client")

DEFAULT_GOOGLE_MODEL = "gemini-2.5-flash"
DEFAULT_OLLAMA_URL = "http://127.0.0.1:11434"
GOOGLE_API_BASE = "https://generativelanguage.googleapis.com/v1beta"


# ---------------------------------------------------------------------------
# Provider config resolution
# ---------------------------------------------------------------------------


class LLMConfig:
    """Normalized provider configuration."""

    def __init__(self, **kwargs):
        self.provider = (kwargs.get("provider") or os.environ.get("LLM_PROVIDER", "google")).strip().lower()
        self.google_api_key = kwargs.get("google_api_key") or os.environ.get("GOOGLE_API_KEY", "")
        self.google_model = kwargs.get("google_model") or os.environ.get("GOOGLE_LLM_MODEL", DEFAULT_GOOGLE_MODEL)
        self.ollama_url = (kwargs.get("ollama_url") or os.environ.get("OLLAMA_URL", DEFAULT_OLLAMA_URL)).rstrip("/")
        self.ollama_model = kwargs.get("ollama_model") or os.environ.get("OLLAMA_MODEL", "")

    @property
    def is_google(self) -> bool:
        return self.provider == "google"

    @property
    def model(self) -> str:
        return self.google_model if self.is_google else self.ollama_model

    def to_dict(self) -> dict:
        return {
            "provider": self.provider,
            "google_api_key": self.google_api_key,
            "google_model": self.google_model,
            "ollama_url": self.ollama_url,
            "ollama_model": self.ollama_model,
        }


# ---------------------------------------------------------------------------
# Google Gemini helpers
# ---------------------------------------------------------------------------


def _google_generate_sync(cfg: LLMConfig, prompt: str, system: str = None,
                          images: list = None) -> str:
    """Call the Gemini generateContent REST API (blocking)."""
    if not cfg.google_api_key:
        raise RuntimeError("Google API key is not configured. Add it in Settings.")
    model = cfg.google_model or DEFAULT_GOOGLE_MODEL

    contents: list = []
    parts: list = []
    if system:
        contents.append({"role": "user", "parts": [{"text": system}]})
    user_parts: list = [{"text": prompt}]
    if images:
        for b64 in images:
            user_parts.append({
                "inline_data": {
                    "mime_type": "image/png",
                    "data": b64,
                }
            })
    contents.append({"role": "user", "parts": user_parts})

    payload = {
        "contents": contents,
        "generationConfig": {"temperature": 0.1},
    }

    url = f"{GOOGLE_API_BASE}/models/{model}:generateContent?key={cfg.google_api_key}"
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=120.0) as response:
        if response.status != 200:
            raise RuntimeError(f"Gemini generation failed with status {response.status}")
        data = json.loads(response.read().decode("utf-8"))
        try:
            return data["candidates"][0]["content"]["parts"][0].get("text", "")
        except (KeyError, IndexError, TypeError) as e:
            raise RuntimeError(f"Unexpected Gemini response shape: {e}")


def _google_list_models_sync(cfg: LLMConfig) -> list:
    """List Gemini models (blocking). Returns model names."""
    if not cfg.google_api_key:
        return []
    url = f"{GOOGLE_API_BASE}/models?key={cfg.google_api_key}"
    req = urllib.request.Request(url)
    try:
        with urllib.request.urlopen(req, timeout=10.0) as response:
            data = json.loads(response.read().decode("utf-8"))
            models = []
            for m in data.get("models", []):
                name = m.get("name", "")
                if name.startswith("models/"):
                    name = name[len("models/"):]
                # Only surface chat-capable generation models
                if ":generateContent" in str(m.get("supportedGenerationMethods", [])):
                    models.append(name)
            return models
    except Exception as e:
        logger.error(f"Failed to list Gemini models: {e}")
        return []


def _google_health_sync(cfg: LLMConfig) -> bool:
    """Check whether the Google API key is valid (blocking)."""
    return bool(cfg.google_api_key and _google_list_models_sync(cfg))


# ---------------------------------------------------------------------------
# Ollama helpers
# ---------------------------------------------------------------------------


def _ollama_generate_sync(cfg: LLMConfig, prompt: str, system: str = None,
                          images: list = None) -> str:
    """Call the Ollama generate API (blocking)."""
    payload = {
        "model": cfg.ollama_model,
        "prompt": prompt,
        "stream": False,
        "options": {"temperature": 0.1},
    }
    if system:
        payload["system"] = system
    if images:
        payload["images"] = images

    req = urllib.request.Request(
        f"{cfg.ollama_url}/api/generate",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=120.0) as response:
        if response.status != 200:
            raise RuntimeError(f"Ollama generation failed with status {response.status}")
        data = json.loads(response.read().decode("utf-8"))
        return data.get("response", "")


def _ollama_list_models_sync(cfg: LLMConfig) -> list:
    """List Ollama models (blocking)."""
    try:
        req = urllib.request.Request(f"{cfg.ollama_url}/api/tags")
        with urllib.request.urlopen(req, timeout=3.0) as response:
            if response.status == 200:
                data = json.loads(response.read().decode("utf-8"))
                return [m.get("name") for m in data.get("models", []) if m.get("name")]
    except Exception as e:
        logger.error(f"Failed to list Ollama models: {e}")
    return []


def _ollama_health_sync(cfg: LLMConfig) -> bool:
    """Check whether Ollama is reachable (blocking)."""
    try:
        req = urllib.request.Request(f"{cfg.ollama_url}/api/tags")
        with urllib.request.urlopen(req, timeout=2.0) as response:
            return response.status == 200
    except Exception:
        return False


# ---------------------------------------------------------------------------
# Public async API
# ---------------------------------------------------------------------------


async def generate(prompt: str, *, model: str = None, provider: str = None,
                   ollama_url: str = None, google_api_key: str = None,
                   system: str = None, images: list = None) -> str:
    """Generate text using the active provider.

    Args:
        prompt: The user prompt.
        model: Override model name.
        provider: ``google`` or ``ollama``.
        ollama_url: Ollama base URL.
        google_api_key: Google AI Studio API key.
        system: Optional system instruction.
        images: Optional list of base64-encoded image strings.

    Returns:
        Generated response text.

    Raises:
        RuntimeError: If the provider fails or is unconfigured.
    """
    cfg = LLMConfig(
        provider=provider,
        ollama_url=ollama_url,
        google_api_key=google_api_key,
    )
    if model:
        if cfg.is_google:
            cfg.google_model = model
        else:
            cfg.ollama_model = model

    if cfg.is_google:
        return await asyncio.get_running_loop().run_in_executor(
            None, lambda: _google_generate_sync(cfg, prompt, system, images)
        )
    return await asyncio.get_running_loop().run_in_executor(
        None, lambda: _ollama_generate_sync(cfg, prompt, system, images)
    )


async def list_models(*, provider: str = None, ollama_url: str = None,
                      google_api_key: str = None) -> list:
    """List available models for the active provider."""
    cfg = LLMConfig(provider=provider, ollama_url=ollama_url, google_api_key=google_api_key)
    if cfg.is_google:
        return await asyncio.get_running_loop().run_in_executor(
            None, lambda: _google_list_models_sync(cfg)
        )
    return await asyncio.get_running_loop().run_in_executor(
        None, lambda: _ollama_list_models_sync(cfg)
    )


async def check_health(*, provider: str = None, ollama_url: str = None,
                       google_api_key: str = None) -> bool:
    """Return whether the active provider is reachable / configured."""
    cfg = LLMConfig(provider=provider, ollama_url=ollama_url, google_api_key=google_api_key)
    if cfg.is_google:
        return await asyncio.get_running_loop().run_in_executor(
            None, lambda: _google_health_sync(cfg)
        )
    return await asyncio.get_running_loop().run_in_executor(
        None, lambda: _ollama_health_sync(cfg)
    )


# ---------------------------------------------------------------------------
# Embeddings (used by RAG ChromaDB when provider is Google)
# ---------------------------------------------------------------------------

DEFAULT_GOOGLE_EMBEDDING_MODEL = "text-embedding-004"


def _google_embed_batch_sync(cfg: LLMConfig, texts: list) -> list:
    """Embed a batch of texts via the Gemini embedding API (blocking)."""
    if not cfg.google_api_key:
        raise RuntimeError("Google API key is not configured for embeddings.")
    model = os.environ.get("GOOGLE_EMBEDDING_MODEL", DEFAULT_GOOGLE_EMBEDDING_MODEL)

    embeddings = []
    # Gemini embedContent accepts one input per call; batch in chunks
    url = f"{GOOGLE_API_BASE}/models/{model}:batchEmbedContents?key={cfg.google_api_key}"
    chunk_size = 100
    for i in range(0, len(texts), chunk_size):
        chunk = texts[i : i + chunk_size]
        payload = {
            "requests": [
                {"model": f"models/{model}", "content": {"parts": [{"text": t}]}}
                for t in chunk
            ]
        }
        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=60.0) as response:
            data = json.loads(response.read().decode("utf-8"))
            for emb in data.get("embeddings", []):
                embeddings.append(emb.get("values", []))
    return embeddings


def _google_embed_query_sync(cfg: LLMConfig, text: str) -> list:
    """Embed a single query via the Gemini embedding API (blocking)."""
    if not cfg.google_api_key:
        raise RuntimeError("Google API key is not configured for embeddings.")
    model = os.environ.get("GOOGLE_EMBEDDING_MODEL", DEFAULT_GOOGLE_EMBEDDING_MODEL)
    url = f"{GOOGLE_API_BASE}/models/{model}:embedContent?key={cfg.google_api_key}"
    payload = {
        "model": f"models/{model}",
        "content": {"parts": [{"text": text}]},
    }
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=30.0) as response:
        data = json.loads(response.read().decode("utf-8"))
        return data.get("embedding", {}).get("values", [])


async def embed_documents(texts: list, *, google_api_key: str = None) -> list:
    """Embed a batch of documents via Google (blocking off the event loop)."""
    cfg = LLMConfig(provider="google", google_api_key=google_api_key)
    return await asyncio.get_running_loop().run_in_executor(
        None, lambda: _google_embed_batch_sync(cfg, texts)
    )


async def embed_query(text: str, *, google_api_key: str = None) -> list:
    """Embed a single query via Google (blocking off the event loop)."""
    cfg = LLMConfig(provider="google", google_api_key=google_api_key)
    return await asyncio.get_running_loop().run_in_executor(
        None, lambda: _google_embed_query_sync(cfg, text)
    )


class GoogleEmbeddingFunction:
    """ChromaDB-compatible embedding function backed by Google embeddings.

    Used by the RAG sidecar when the active provider is Google so the vector
    store is fully cloud-based (no local ONNX model load).
    """

    def __init__(self, google_api_key: str = ""):
        self._key = google_api_key or os.environ.get("GOOGLE_API_KEY", "")

    def __call__(self, input):
        cfg = LLMConfig(provider="google", google_api_key=self._key)
        if isinstance(input, str):
            return [_google_embed_query_sync(cfg, input)]
        return _google_embed_batch_sync(cfg, list(input))
