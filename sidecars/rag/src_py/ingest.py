"""Ingest Module

Handles document ingestion for the RAG sidecar.  Reads a file from disk,
extracts text, splits it into chunks, and stores the chunks in ChromaDB
via ``ChromaClient``.

Progress events are emitted via the events module for IPC.
"""

import os
import logging
import pypdf
from typing import List, Dict

from sidecars.rag.src_py.chroma_client import ChromaClient
from sidecars.rag.src_py.events import emit_progress, emit_warning

logger = logging.getLogger("rag.ingest")


async def ingest_document(rfp_id: str, file_path: str, google_api_key: str = "") -> dict:
    """Ingest a document into the RAG pipeline.

    Args:
        rfp_id: Unique identifier for the RFP.
        file_path: Absolute path to the file to ingest.

    Returns:
        A dict with key ``chunksProcessed`` indicating how many
        chunks were stored.

    Raises:
        FileNotFoundError: If *file_path* does not exist.
        RuntimeError: If ChromaDB storage fails.
    """
    emit_progress(f"Starting ingestion for {file_path}")

    if not os.path.exists(file_path):
        raise FileNotFoundError(f"File not found: {file_path}")

    _, ext = os.path.splitext(file_path)

    emit_progress(f"Parsing {ext} file...")

    # 1. Text Extraction
    extracted_text = _extract_text(file_path)

    emit_progress("Chunking text...")

    # 2. Chunking
    chunks = _chunk_text(extracted_text, rfp_id)

    emit_progress("Generating embeddings and storing...")

    # 3. Store in Chroma
    try:
        chroma = ChromaClient(google_api_key=google_api_key)
        is_chroma_up = await chroma.check_health()

        if is_chroma_up:
            collection = await chroma.get_or_create_collection(
                f"rfp_{rfp_id}"
            )
            ids = [c["id"] for c in chunks]
            documents = [c["text"] for c in chunks]
            metadatas = [
                {"chunkIndex": i, "source": file_path}
                for i, _ in enumerate(chunks)
            ]

            await collection.upsert(
                ids=ids, documents=documents, metadatas=metadatas
            )
        else:
            emit_warning(
                "ChromaDB is not running. Ingestion skipped storage phase."
            )
    except Exception as err:
        logger.error(f"Ingestion failed: {err}")
        raise

    emit_progress(
        f"Ingestion complete. Processed {len(chunks)} chunks."
    )

    return {"chunksProcessed": len(chunks)}


def _extract_text(file_path: str) -> str:
    """Extract text from a file, supporting PDF and plain text formats.

    Args:
        file_path: Path to the file.

    Returns:
        Extracted text content.
    """
    extracted_text = ""
    try:
        with open(file_path, "rb") as f:
            reader = pypdf.PdfReader(f)
            for page in reader.pages:
                text = page.extract_text()
                if text:
                    extracted_text += text + "\n"
    except Exception as e:
        logger.error(f"Failed parsing PDF {file_path}: {e}")
        extracted_text = ""

    if not extracted_text.strip():
        try:
            with open(
                file_path, "r", encoding="utf-8", errors="ignore"
            ) as f:
                extracted_text = f.read()
        except Exception as e:
            logger.error(f"Failed to read file as text: {e}")
            extracted_text = (
                f"Unparseable file: {os.path.basename(file_path)}"
            )

    return extracted_text


def _chunk_text(text: str, rfp_id: str) -> List[Dict[str, str]]:
    """Split text into overlapping chunks for embedding storage.

    Uses a simple word-based chunking strategy with overlap.

    Args:
        text: The full extracted text.
        rfp_id: RFP identifier for generating chunk IDs.

    Returns:
        List of dicts with ``text`` and ``id`` keys.
    """
    chunk_size = 1500
    chunk_overlap = 150
    chunks: List[Dict[str, str]] = []

    words = text.split()
    current_chunk: List[str] = []
    current_len = 0
    chunk_idx = 0

    for word in words:
        current_chunk.append(word)
        current_len += len(word) + 1
        if current_len >= chunk_size:
            chunks.append(
                {
                    "text": " ".join(current_chunk),
                    "id": f"{rfp_id}-chunk-{chunk_idx}",
                }
            )
            chunk_idx += 1
            overlap_words = (
                current_chunk[-30:] if len(current_chunk) > 30 else []
            )
            current_chunk = overlap_words
            current_len = sum(len(w) + 1 for w in overlap_words)

    if current_chunk:
        chunks.append(
            {
                "text": " ".join(current_chunk),
                "id": f"{rfp_id}-chunk-{chunk_idx}",
            }
        )

    return chunks
