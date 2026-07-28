"""ChromaDB Utility Module for Gap Engine

Provides ChromaDB query operations for retrieving RFP document context
during gap analysis.  Decoupled from the RAG sidecar's internal DB_PATH.
"""

import logging
from typing import Optional

logger = logging.getLogger("gap_engine.chroma_utils")

# Can be overridden via environment or passed explicitly
DEFAULT_DB_PATH = None


def query_rfp_context(
    rfp_id: str,
    db_path: Optional[str] = None,
    n_results: int = 10,
) -> str:
    """Query ChromaDB for relevant document chunks for a given RFP.

    Args:
        rfp_id: RFP identifier.
        db_path: Path to the ChromaDB persistent directory.
                 Falls back to DEFAULT_DB_PATH, then to RAG's DB_PATH.
        n_results: Number of chunks to retrieve.

    Returns:
        Concatenated document text, or empty string if not found or unavailable.
    """
    if db_path is None:
        db_path = DEFAULT_DB_PATH
    if db_path is None:
        try:
            from sidecars.rag.src_py.chroma_client import DB_PATH as _rag_path
            db_path = _rag_path
        except ImportError:
            logger.warning("RAG sidecar not available; cannot resolve DB_PATH")
            return ""

    try:
        import chromadb
        client = chromadb.PersistentClient(path=db_path)
        col_name = f"rfp_{rfp_id}"
        collections = [c.name for c in client.list_collections()]

        if col_name not in collections:
            logger.warning(f"ChromaDB collection '{col_name}' does not exist yet.")
            return ""

        collection = client.get_or_create_collection(name=col_name)
        res = collection.query(
            query_texts=[
                "compliance", "requirements", "security",
                "sla", "liability", "audit"
            ],
            n_results=n_results,
        )
        docs = res.get("documents", [[]])[0]
        if docs:
            context = "\n\n".join(docs)
            logger.info(
                f"Retrieved {len(docs)} relevant chunks from ChromaDB for {rfp_id}."
            )
            return context
    except Exception as e:
        logger.error(f"Failed to query ChromaDB for gaps: {e}")

    return ""
