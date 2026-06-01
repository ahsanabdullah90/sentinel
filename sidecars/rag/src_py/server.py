"""RAG JSON-RPC Server Module

Provides RAG endpoints via standard input/output streams.
"""

import asyncio
import logging
import os
import sys
import json
import traceback
import tempfile

from .ingest import ingest_document
from .ollama_client import OllamaClient
from .chroma_client import ChromaClient

# ---------------------------------------------------------------------------
# IPC Hijack & Safety Redirection
# ---------------------------------------------------------------------------
ipc_out = sys.stdout
sys.stdout = sys.stderr

class JsonFormatter(logging.Formatter):
    def format(self, record):
        log_record = {
            "timestamp": self.formatTime(record, self.datefmt),
            "level": record.levelname,
            "module": record.module,
            "message": record.getMessage()
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
        _emit_ipc({
            "error": {"message": "Missing document_id or content"},
            "req_id": req_id
        })
        return

    logger.info(f"JSON-RPC Ingest request received for document: {document_id}")
    
    temp_file = tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False, encoding="utf-8")
    temp_file_path = temp_file.name
    
    try:
        temp_file.write(content)
        temp_file.close()
        
        await ingest_document(document_id, temp_file_path)
        _emit_ipc({
            "result": {"status": "ok"},
            "req_id": req_id
        })
    except Exception as e:
        logger.error(f"Error in JSON-RPC Ingest: {str(e)}")
        _emit_ipc({
            "error": {"message": str(e)},
            "req_id": req_id
        })
    finally:
        if os.path.exists(temp_file_path):
            try:
                os.remove(temp_file_path)
            except Exception as ex:
                logger.warning(f"Failed to delete temp file {temp_file_path}: {ex}")

async def handle_query(params: dict, req_id: str):
    query = params.get("query")
    if not query:
        _emit_ipc({
            "error": {"message": "Missing query"},
            "req_id": req_id
        })
        return

    logger.info(f"JSON-RPC Query request received: {query}")

    try:
        ollama = OllamaClient()
        chroma = ChromaClient()

        context_text = "No specific context available."
        source_docs_list = []
        is_chroma_up = await chroma.check_health()
        
        if is_chroma_up:
            collections = await chroma.list_collections()
            retrieved_contexts = []
            for col_info in collections:
                col_name = col_info.get("name", "")
                if col_name.startswith("rfp_"):
                    try:
                        collection = await chroma.get_or_create_collection(col_name)
                        query_results = await collection.query(query_texts=[query], n_results=3)
                        
                        docs = query_results.get("documents", [[]])[0]
                        ids = query_results.get("ids", [[]])[0]
                        distances = query_results.get("distances", [[]])[0] if "distances" in query_results else [0.5] * len(docs)
                        metadatas = query_results.get("metadatas", [[]])[0] if "metadatas" in query_results else [{}] * len(docs)
                        
                        for doc, doc_id, dist, meta in zip(docs, ids, distances, metadatas):
                            retrieved_contexts.append(doc)
                            source_docs_list.append({
                                "id": doc_id,
                                "score": dist,
                                "source": meta.get("source", "unknown"),
                                "collection": col_name
                            })
                    except Exception as col_err:
                        logger.error(f"Failed to query collection {col_name}: {col_err}")
            
            if retrieved_contexts:
                context_text = "\n\n".join(retrieved_contexts)

        prompt = f"Based on the following context, answer the query.\nContext: {context_text}\nQuery: {query}"

        pulled_models = await ollama.get_pulled_models()
        if not pulled_models:
            raise Exception("No pulled models found in Ollama.")

        selected_model = "llama3.1:8b"
        found_model = False
        
        preferred_candidates = ["qwen2.5-coder", "gemma", "deepseek", "phi3", "llama3.1:8b", "llama3", "mistral"]
        for pref in preferred_candidates:
            matched = [m for m in pulled_models if pref in m.lower() or m == pref]
            if matched:
                selected_model = matched[0]
                found_model = True
                break
        
        if not found_model and pulled_models:
            selected_model = pulled_models[0]

        logger.info(f"Generating Ollama answer using model: {selected_model}")
        answer = await ollama.generate(
            model=selected_model,
            prompt=prompt,
            system_context="You are an expert proposal assistant."
        )

        source_documents = json.dumps(source_docs_list if source_docs_list else [{"id": "empty", "score": 1.0}])
        _emit_ipc({
            "result": {
                "answer": answer,
                "source_documents": source_documents
            },
            "req_id": req_id
        })
    except Exception as e:
        logger.error(f"Error in JSON-RPC Query: {str(e)}")
        _emit_ipc({
            "error": {"message": str(e)},
            "req_id": req_id
        })

def _emit_ipc(data: dict):
    try:
        ipc_out.write(json.dumps(data) + "\n")
        ipc_out.flush()
    except Exception as e:
        logger.error(f"Failed to write IPC message: {e}")

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
                
            line_str = line.decode('utf-8').strip()
            if not line_str:
                continue

            try:
                req = json.loads(line_str)
                method = req.get("method")
                params = req.get("params", {})
                req_id = req.get("id", "")

                if method == "ingest":
                    task = asyncio.create_task(handle_ingest(params, req_id))
                    active_tasks.add(task)
                    task.add_done_callback(active_tasks.discard)
                elif method == "query":
                    task = asyncio.create_task(handle_query(params, req_id))
                    active_tasks.add(task)
                    task.add_done_callback(active_tasks.discard)
                else:
                    logger.warning(f"Unknown JSON-RPC method: {method}")
                    _emit_ipc({
                        "error": {"message": f"Unknown method: {method}"},
                        "req_id": req_id
                    })
            except json.JSONDecodeError:
                logger.warning(f"Received invalid JSON on stdin: {line_str}")
            except Exception as e:
                logger.error(f"Error processing IPC request: {str(e)}\n{traceback.format_exc()}")
                
    except asyncio.CancelledError:
        logger.info("Main IPC loop cancelled.")
    finally:
        for task in active_tasks:
            task.cancel()
        if active_tasks:
            await asyncio.gather(*active_tasks, return_exceptions=True)
        logger.info("RAG JSON-RPC Server gracefully shutdown.")

if __name__ == "__main__":
    try:
        asyncio.run(serve())
    except KeyboardInterrupt:
        pass
