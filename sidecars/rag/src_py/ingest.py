import os
import json
import logging
from .chroma_client import ChromaClient

logger = logging.getLogger("rag.ingest")

async def ingest_document(rfp_id: str, file_path: str) -> dict:
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

    # 1. Stub extraction matching TS Behavior
    extracted_text = f"This is mock extracted text for RFP {rfp_id} from {file_path}."

    print(json.dumps({
        "event": "progress",
        "portalId": "rag",
        "message": "Chunking text..."
    }), flush=True)

    # 2. Stub chunking matching TS Behavior
    chunks = [{"text": extracted_text, "id": f"{rfp_id}-chunk-0"}]

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
