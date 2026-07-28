"""Gap Analyzer Module

Core business logic for compliance gap analysis.
Coordinates ChromaDB context retrieval and Ollama inference.
"""

import logging
from typing import List, Dict, Optional

from sidecars.gap_engine.src_py.chroma_utils import query_rfp_context
from sidecars.gap_engine.src_py.ollama_utils import generate_gaps
from sidecars.gap_engine.src_py.events import emit_gap_report

logger = logging.getLogger("gap_engine.analyzer")


def analyze_gaps(
    rfp_id: str,
    ollama_url: str = "http://127.0.0.1:11434",
    model_name: str = "llama3",
    db_path: Optional[str] = None,
) -> List[Dict[str, str]]:
    """Analyze compliance and requirements gaps for a given RFP.

    Steps:
        1. Fetch document chunks from ChromaDB for context.
        2. Send zero-shot auditing prompt to Ollama.
        3. Parse and validate the response.
        4. Emit gap report event via IPC.
        5. Fall back to generic warnings if inference fails.

    Args:
        rfp_id: Identifier of the RFP to analyze.
        ollama_url: Ollama API endpoint URL.
        model_name: Ollama model tag.
        db_path: ChromaDB persistent directory path (optional).

    Returns:
        A list of dicts with ``area`` and ``description`` keys.
    """
    logger.info(
        f"Analyzing gaps for RFP {rfp_id} using {model_name} at {ollama_url}"
    )

    context_text = query_rfp_context(rfp_id, db_path=db_path)
    gaps = generate_gaps(rfp_id, context_text, ollama_url, model_name)

    emit_gap_report(rfp_id, gaps)
    return gaps
