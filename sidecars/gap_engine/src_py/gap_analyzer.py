"""Gap Analyzer Module

Core business logic for compliance gap analysis.
Coordinates ChromaDB context retrieval and LLM inference (Google Gemini or Ollama).
"""

import json
import logging
from typing import List, Dict, Optional

from sidecars.gap_engine.src_py.chroma_utils import query_rfp_context
from sidecars.gap_engine.src_py.events import emit_gap_report
from sidecars.shared.llm_client import LLMConfig

logger = logging.getLogger("gap_engine.analyzer")

FALLBACK_GAPS = [
    {"area": "Security", "description": "Missing details on data encryption at rest."},
    {"area": "Compliance", "description": "FedRAMP level not specified."},
]


def analyze_gaps(
    rfp_id: str,
    ollama_url: str = "http://127.0.0.1:11434",
    model_name: str = "gemma3:4b",
    db_path: Optional[str] = None,
    provider_config: dict = None,
) -> List[Dict[str, str]]:
    """Analyze compliance and requirements gaps for a given RFP.

    Steps:
        1. Fetch document chunks from ChromaDB for context.
        2. Send zero-shot auditing prompt to the active LLM provider.
        3. Parse and validate the response.
        4. Emit gap report event via IPC.
        5. Fall back to generic warnings if inference fails.

    Args:
        rfp_id: Identifier of the RFP to analyze.
        ollama_url: Ollama API endpoint URL (used when provider is Ollama).
        model_name: Ollama model tag.
        db_path: ChromaDB persistent directory path (optional).
        provider_config: Optional dict with provider settings
            (``provider``, ``google_api_key``, ``google_model``, etc.).

    Returns:
        A list of dicts with ``area`` and ``description`` keys.
    """
    cfg = LLMConfig(**(provider_config or {}))

    # Preserve explicit args when provider config does not override them
    if cfg.provider != "google":
        cfg.ollama_url = ollama_url or cfg.ollama_url
        cfg.ollama_model = model_name or cfg.ollama_model

    logger.info(
        f"Analyzing gaps for RFP {rfp_id} using {cfg.model or 'default'} on {cfg.provider}"
    )

    context_text = query_rfp_context(rfp_id, db_path=db_path)
    gaps = _generate_gaps(rfp_id, context_text, cfg)

    emit_gap_report(rfp_id, gaps)
    return gaps


def _generate_gaps(
    rfp_id: str,
    context_text: str,
    cfg: LLMConfig,
) -> List[Dict[str, str]]:
    """Analyze RFP context for compliance gaps using the active provider."""
    if not context_text:
        context_text = (
            "No document text available. "
            "Document has not been ingested or is empty."
        )

    prompt = _build_prompt(context_text)

    import asyncio

    try:
        from sidecars.shared.llm_client import generate

        loop = asyncio.get_event_loop()
        raw_response = loop.run_until_complete(
            generate(
                prompt,
                model=cfg.model,
                provider=cfg.provider,
                ollama_url=cfg.ollama_url,
                google_api_key=cfg.google_api_key,
            )
        )
        gaps = _parse_response(raw_response)
        if gaps:
            return gaps
    except Exception as err:
        logger.error(f"LLM compliance inference failed: {err}")

    return list(FALLBACK_GAPS)


def _build_prompt(context_text: str) -> str:
    """Build the zero-shot auditing prompt."""
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
    """Parse and validate the LLM JSON response.

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
