"""Ollama Utility Module for Gap Engine

Provides synchronous HTTP helpers for querying Ollama during gap analysis.
Designed to be called via ``run_in_executor`` from async code.
"""

import json
import logging
import urllib.request
from typing import List, Dict

logger = logging.getLogger("gap_engine.ollama_utils")

FALLBACK_GAPS = [
    {"area": "Security", "description": "Missing details on data encryption at rest."},
    {"area": "Compliance", "description": "FedRAMP level not specified."},
]


def generate_gaps(
    rfp_id: str,
    context_text: str,
    ollama_url: str = "http://127.0.0.1:11434",
    model_name: str = "gemma3:4b",
) -> List[Dict[str, str]]:
    """Analyze RFP context for compliance gaps using Ollama.

    Args:
        rfp_id: RFP identifier (for logging and event context).
        context_text: Retrieved ChromaDB document text.
        ollama_url: Ollama API base URL.
        model_name: Ollama model tag.

    Returns:
        List of dicts with ``area`` and ``description`` keys.
        Falls back to generic warnings if inference fails.
    """
    logger.info(
        f"Analyzing gaps for RFP {rfp_id} using {model_name} at {ollama_url}"
    )

    if not context_text:
        context_text = (
            "No document text available. "
            "Document has not been ingested or is empty."
        )

    prompt = _build_prompt(context_text)

    payload = {
        "model": model_name or "gemma3:4b",
        "prompt": prompt,
        "stream": False,
        "options": {"temperature": 0.1},
    }

    try:
        req = urllib.request.Request(
            f"{ollama_url.rstrip('/')}/api/generate",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=45.0) as response:
            response_body = response.read().decode("utf-8")
            res_data = json.loads(response_body)
            raw_response = res_data.get("response", "").strip()

        gaps = _parse_response(raw_response)
        if gaps:
            return gaps
    except Exception as err:
        logger.error(f"Ollama compliance inference failed: {err}")

    return list(FALLBACK_GAPS)


def _build_prompt(context_text: str) -> str:
    """Build the zero-shot auditing prompt for Ollama."""
    return f"""
[SYSTEM CONTEXT]
You are an expert compliance auditor. Analyze the following RFP document text and extract any compliance gaps, missing details, or risks (e.g. security details, FedRAMP levels, SLA conditions, background check rules, data encryption requirements).

[DOCUMENT CONTENT]
{context_text[:12000]}

[OUTPUT FORMAT]
Output ONLY a valid JSON array of objects with keys "area" and "description". Do not include markdown wraps, code block styling, or any conversational text.
Example:
[
  {{"area": "Security", "description": "No details on data encryption at rest."}},
  {{"area": "Compliance", "description": "FedRAMP level not specified."}}
]
"""


def _parse_response(raw_response: str) -> List[Dict[str, str]]:
    """Parse and validate the Ollama JSON response.

    Strips markdown code fences if present.
    Returns only items with valid ``area`` and ``description`` keys.
    """
    cleaned = raw_response
    if "```json" in cleaned:
        cleaned = cleaned.split("```json")[1].split("```")[0].strip()
    elif "```" in cleaned:
        cleaned = cleaned.split("```")[1].split("```")[0].strip()

    try:
        parsed = json.loads(cleaned)
    except (json.JSONDecodeError, Exception):
        return []

    if not isinstance(parsed, list):
        return []

    valid = []
    for g in parsed:
        if isinstance(g, dict) and "area" in g and "description" in g:
            valid.append({
                "area": str(g["area"]),
                "description": str(g["description"]),
            })
    return valid
