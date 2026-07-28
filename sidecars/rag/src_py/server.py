"""RAG JSON-RPC Server Module

Provides RAG endpoints via standard input/output streams.
"""

import asyncio
import json
import logging
import os
import sys
import tempfile
import traceback

from sidecars.rag.src_py.ingest import ingest_document
from sidecars.rag.src_py.ollama_client import OllamaClient
from sidecars.rag.src_py.chroma_client import ChromaClient
from sidecars.rag.src_py.events import (
    _emit_ipc,
    emit_progress,
    emit_result,
    emit_error_response,
)

# ---------------------------------------------------------------------------
# IPC Hijack & Safety Redirection
# ---------------------------------------------------------------------------
# We capture the original stdout for pure JSON-RPC IPC.
# We redirect sys.stdout to sys.stderr so that stray print() statements
# do not corrupt the JSON stream.
ipc_out = sys.stdout
sys.stdout = sys.stderr


class JsonFormatter(logging.Formatter):
    def format(self, record):
        log_record = {
            "timestamp": self.formatTime(record, self.datefmt),
            "level": record.levelname,
            "module": record.module,
            "message": record.getMessage(),
        }
        if record.exc_info:
            log_record["exc_info"] = self.formatException(record.exc_info)
        return json.dumps(log_record)


handler = logging.StreamHandler(sys.stderr)
handler.setFormatter(JsonFormatter())
logger = logging.getLogger("rag.server")
logger.setLevel(logging.INFO)
logger.addHandler(handler)
logger.propagate = False


# ---------------------------------------------------------------------------
# Handlers
# ---------------------------------------------------------------------------


async def handle_ingest(params: dict, req_id: str):
    document_id = params.get("document_id")
    content = params.get("content")

    if not document_id or not content:
        emit_error_response("Missing document_id or content", req_id)
        return

    logger.info(f"JSON-RPC Ingest request received for document: {document_id}")

    temp_file_path = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".txt", delete=False, encoding="utf-8"
        ) as f:
            f.write(content)
            temp_file_path = f.name

        await ingest_document(document_id, temp_file_path)
        emit_result({"status": "ok"}, req_id)
    except Exception as e:
        logger.error(f"Error in JSON-RPC Ingest: {str(e)}")
        emit_error_response(str(e), req_id)
    finally:
        if temp_file_path and os.path.exists(temp_file_path):
            try:
                os.remove(temp_file_path)
            except Exception as ex:
                logger.warning(f"Failed to delete temp file {temp_file_path}: {ex}")


async def handle_query(params: dict, req_id: str):
    query = params.get("query")
    if not query:
        emit_error_response("Missing query", req_id)
        return

    logger.info(f"JSON-RPC Query request received: {query}")

    try:
        result = await _execute_query(query)
        emit_result(result, req_id)
    except Exception as e:
        logger.error(f"Error in JSON-RPC Query: {str(e)}")
        emit_error_response(str(e), req_id)


async def _execute_query(query: str) -> dict:
    """Execute a full RAG query pipeline.

    Steps:
        1. Query ChromaDB for relevant context from all RFP collections.
        2. Select the best available Ollama model.
        3. Generate an answer using the retrieved context.
    """
    ollama = OllamaClient()
    chroma = ChromaClient()

    context_text = "No specific context available."
    source_docs_list = []
    is_chroma_up = await chroma.check_health()

    if is_chroma_up:
        retrieved_contexts, source_docs_list = await _query_chromadb(
            chroma, query
        )
        if retrieved_contexts:
            context_text = "\n\n".join(retrieved_contexts)

    prompt = (
        f"Based on the following context, answer the query.\n"
        f"Context: {context_text}\nQuery: {query}"
    )

    pulled_models = await ollama.get_pulled_models()
    if not pulled_models:
        raise RuntimeError("No pulled models found in Ollama.")

    selected_model = _pick_best_model(pulled_models)

    logger.info(f"Generating Ollama answer using model: {selected_model}")
    answer = await ollama.generate(
        model=selected_model,
        prompt=prompt,
        system_context="You are an expert proposal assistant.",
    )

    if not source_docs_list:
        source_docs_list = [{"id": "empty", "score": 1.0}]

    return {"answer": answer, "source_documents": json.dumps(source_docs_list)}


async def _query_chromadb(chroma, query: str):
    """Query all RFP collections in ChromaDB and return (contexts, source_docs)."""
    collections = await chroma.list_collections()
    retrieved_contexts = []
    source_docs_list = []

    for col_info in collections:
        col_name = col_info.get("name", "")
        if not col_name.startswith("rfp_"):
            continue

        try:
            collection = await chroma.get_or_create_collection(col_name)
            query_results = await collection.query(
                query_texts=[query], n_results=3
            )

            docs = query_results.get("documents", [[]])[0]
            ids = query_results.get("ids", [[]])[0]
            distances = (
                query_results.get("distances", [[]])[0]
                if "distances" in query_results
                else [0.5] * len(docs)
            )
            metadatas = (
                query_results.get("metadatas", [[]])[0]
                if "metadatas" in query_results
                else [{}] * len(docs)
            )

            for doc, doc_id, dist, meta in zip(
                docs, ids, distances, metadatas
            ):
                retrieved_contexts.append(doc)
                source_docs_list.append(
                    {
                        "id": doc_id,
                        "score": dist,
                        "source": meta.get("source", "unknown"),
                        "collection": col_name,
                    }
                )
        except Exception as col_err:
            logger.error(f"Failed to query collection {col_name}: {col_err}")

    return retrieved_contexts, source_docs_list


def _pick_best_model(pulled_models: list) -> str:
    """Pick the best available Ollama model based on a preference list.

    Falls back to the first available model if no preferred model is found.
    """
    preferred_candidates = [
        "qwen2.5-coder",
        "gemma",
        "deepseek",
        "phi3",
        "llama3.1:8b",
        "llama3",
        "mistral",
    ]
    for pref in preferred_candidates:
        matched = [
            m for m in pulled_models if pref in m.lower() or m == pref
        ]
        if matched:
            return matched[0]
    return pulled_models[0] if pulled_models else "llama3.1:8b"


# ---------------------------------------------------------------------------
# Main IPC Loop
# ---------------------------------------------------------------------------


async def serve():
    logger.info("RAG JSON-RPC Server started over stdin/stdout.")
    _emit_ipc({"event": "ready"})

    active_tasks = set()
    loop = asyncio.get_running_loop()
    reader = asyncio.StreamReader()
    protocol = asyncio.StreamReaderProtocol(reader)
    await loop.connect_read_pipe(lambda: protocol, sys.stdin)

    try:
        while True:
            line = await reader.readline()
            if not line:
                logger.info("EOF received on stdin. Shutting down.")
                break

            line_str = line.decode("utf-8").strip()
            if not line_str:
                continue

            try:
                req = json.loads(line_str)
                method = req.get("method")
                params = req.get("params", {})
                req_id = req.get("id", "")

                if method == "ingest":
                    task = asyncio.create_task(
                        handle_ingest(params, req_id)
                    )
                    active_tasks.add(task)
                    task.add_done_callback(active_tasks.discard)
                elif method == "query":
                    task = asyncio.create_task(
                        handle_query(params, req_id)
                    )
                    active_tasks.add(task)
                    task.add_done_callback(active_tasks.discard)
                else:
                    logger.warning(f"Unknown JSON-RPC method: {method}")
                    _emit_ipc({
                        "error": {
                            "message": f"Unknown method: {method}"
                        },
                        "req_id": req_id,
                    })
            except json.JSONDecodeError:
                logger.warning(
                    f"Received invalid JSON on stdin: {line_str}"
                )
            except Exception as e:
                logger.error(
                    f"Error processing IPC request: {str(e)}\n{traceback.format_exc()}"
                )

    except asyncio.CancelledError:
        logger.info("Main IPC loop cancelled.")
    finally:
        for task in active_tasks:
            task.cancel()
        if active_tasks:
            await asyncio.gather(
                *active_tasks, return_exceptions=True
            )
        logger.info("RAG JSON-RPC Server gracefully shutdown.")


if __name__ == "__main__":
    try:
        asyncio.run(serve())
    except KeyboardInterrupt:
        pass
