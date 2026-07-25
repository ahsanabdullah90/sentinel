"""Ingest Module

Handles document ingestion for the RAG sidecar.  Reads a file from disk,
extracts text, splits it into chunks, and stores the chunks in ChromaDB
via ``ChromaClient``.

Progress events are emitted as JSON lines on stdout.
"""

import os
import json
import logging
import pypdf
from sidecars.rag.src_py.chroma_client import ChromaClient

logger = logging.getLogger("rag.ingest")


async def ingest_document(rfp_id: str, file_path: str) -> dict:
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
    print(json.dumps({
        "event": "progress",
        "portalId": "rag",
        "message": f"Starting ingestion for {file_path} (Python)"
    }), flush=True)

    if not os.path.exists(file_path):
        raise FileNotFoundError(f"File not found: {file_path}")

    _, ext = os.path.splitext(file_path)
    ext = ext.lower()

    print(json.dumps({
        "event": "progress",
        "portalId": "rag",
        "message": f"Parsing {ext} file..."
    }), flush=True)

    # 1. Real Text Extraction (pypdf)
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
        # Try as plain text file fallback
        try:
            with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                extracted_text = f.read()
        except Exception as e:
            logger.error(f"Failed to read file as text: {e}")
            extracted_text = f"Unparseable file: {os.path.basename(file_path)}"

    print(json.dumps({
        "event": "progress",
        "portalId": "rag",
        "message": "Chunking text..."
    }), flush=True)

    # 2. Recursive-Character Chunking
    chunk_size = 1500
    chunk_overlap = 150
    chunks = []
    
    words = extracted_text.split()
    current_chunk = []
    current_len = 0
    chunk_idx = 0
    
    for word in words:
        current_chunk.append(word)
        current_len += len(word) + 1
        if current_len >= chunk_size:
            chunks.append({
                "text": " ".join(current_chunk),
                "id": f"{rfp_id}-chunk-{chunk_idx}"
            })
            chunk_idx += 1
            current_chunk = current_chunk[-30:] if len(current_chunk) > 30 else []
            current_len = sum(len(w) + 1 for w in current_chunk)
            
    if current_chunk:
        chunks.append({
            "text": " ".join(current_chunk),
            "id": f"{rfp_id}-chunk-{chunk_idx}"
        })

    print(json.dumps({
        "event": "progress",
        "portalId": "rag",
        "message": "Generating embeddings and storing..."
    }), flush=True)

    # 3. Store in Chroma
    try:
        chroma = ChromaClient()
        is_chroma_up = await chroma.check_health()

        if is_chroma_up:
            collection = await chroma.get_or_create_collection(f"rfp_{rfp_id}")
            ids = [c["id"] for c in chunks]
            documents = [c["text"] for c in chunks]
            metadatas = [{"chunkIndex": i, "source": file_path} for i, _ in enumerate(chunks)]

            await collection.upsert(
                ids=ids,
                documents=documents,
                metadatas=metadatas
            )
        else:
            print(json.dumps({
                "event": "warning",
                "message": "ChromaDB is not running. Ingestion skipped storage phase."
            }), flush=True)
    except Exception as err:
        print(json.dumps({
            "level": "error",
            "msg": "Ingestion failed",
            "ctx": str(err)
        }), flush=True)
        raise

    print(json.dumps({
        "event": "progress",
        "portalId": "rag",
        "message": f"Ingestion complete. Processed {len(chunks)} chunks."
    }), flush=True)

    return {"chunksProcessed": len(chunks)}
