"""Tests for the RAG utilities module."""

import os

from sidecars.rag.src_py.utils import resolve_ollama_url


def test_resolve_ollama_url_default():
    url = resolve_ollama_url(None)
    assert url == "http://localhost:11434"


def test_resolve_ollama_url_custom():
    url = resolve_ollama_url("http://my-ollama:11434")
    assert url == "http://my-ollama:11434"


def test_resolve_ollama_url_keeps_non_localhost():
    url = resolve_ollama_url("http://ollama-service:11434")
    assert url == "http://ollama-service:11434"


def test_resolve_ollama_url_docker_disabled():
    old = os.environ.get("RUNNING_IN_DOCKER")
    try:
        if "RUNNING_IN_DOCKER" in os.environ:
            del os.environ["RUNNING_IN_DOCKER"]
        url = resolve_ollama_url("http://localhost:11434")
        assert url == "http://localhost:11434"
    finally:
        if old is not None:
            os.environ["RUNNING_IN_DOCKER"] = old


def test_resolve_ollama_url_env_var():
    old = os.environ.get("OLLAMA_URL")
    try:
        if old is not None:
            del os.environ["OLLAMA_URL"]
        url = resolve_ollama_url(None)
        assert url == "http://localhost:11434"
    finally:
        if old is not None:
            os.environ["OLLAMA_URL"] = old


def test_resolve_ollama_url_with_env_set():
    old = os.environ.get("OLLAMA_URL")
    try:
        os.environ["OLLAMA_URL"] = "http://custom:8080"
        url = resolve_ollama_url(None)
        assert url == "http://custom:8080"
    finally:
        if old is not None:
            os.environ["OLLAMA_URL"] = old
        else:
            del os.environ["OLLAMA_URL"]
