"""Ollama Utility Module

Provides synchronous HTTP helpers for communicating with the Ollama API
and JSON extraction utilities used by the Hunter scraper strategies.
"""

import json
import re
import logging
import urllib.request
from typing import List, Any

logger = logging.getLogger("hunter.ollama_utils")


def extract_json(text: str) -> Any:
    """Parse JSON from *text*, tolerating markdown code-fences.

    Args:
        text: Raw text potentially containing fenced JSON.

    Returns:
        The parsed Python object (list or dict).

    Raises:
        ValueError: If no valid JSON can be extracted.
    """
    try:
        match = re.search(r"```(?:json)?\s*([\s\S]+?)\s*```", text)
        raw = match.group(1) if match else text
        return json.loads(raw.strip())
    except Exception as err:
        start_brace = text.find("{")
        start_bracket = text.find("[")

        if start_brace == -1:
            start = start_bracket
        elif start_bracket == -1:
            start = start_brace
        else:
            start = min(start_brace, start_bracket)

        end_brace = text.rfind("}")
        end_bracket = text.rfind("]")

        if end_brace == -1:
            end = end_bracket
        elif end_bracket == -1:
            end = end_brace
        else:
            end = max(end_brace, end_bracket)

        if start != -1 and end != -1 and end > start:
            try:
                return json.loads(text[start : end + 1])
            except Exception:
                raise ValueError(f"Failed to parse JSON: {str(err)}")
        raise err


def fetch_ollama_tags_sync(ollama_url: str) -> List[str]:
    """Fetch available Ollama models via blocking HTTP, off the event loop.

    Args:
        ollama_url: Base URL of the Ollama server.

    Returns:
        List of model name strings, or empty list on failure.
    """
    clean_url = ollama_url.rstrip("/")
    try:
        req = urllib.request.Request(f"{clean_url}/api/tags")
        with urllib.request.urlopen(req, timeout=3.0) as response:
            if response.status == 200:
                data = json.loads(response.read().decode("utf-8"))
                return [m["name"] for m in data.get("models", [])]
    except Exception as e:
        logger.error(f"Failed to query Ollama models at {ollama_url}: {str(e)}")
    return []


def fetch_ollama_generate_sync(ollama_url: str, payload: dict) -> str:
    """Generate text via Ollama using blocking HTTP, off the event loop.

    Args:
        ollama_url: Base URL of the Ollama server.
        payload: The JSON payload for /api/generate.

    Returns:
        The response text, or empty string on failure.
    """
    clean_url = ollama_url.rstrip("/")
    try:
        req = urllib.request.Request(
            f"{clean_url}/api/generate",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=120.0) as response:
            if response.status == 200:
                resp_data = json.loads(response.read().decode("utf-8"))
                return resp_data.get("response", "").strip()
    except Exception as e:
        logger.error(f"Failed to perform Ollama generation at {ollama_url}: {str(e)}")
    return ""
