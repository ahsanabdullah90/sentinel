# RAG Sidecar — Local Retrieval-Augmented Generation

The **RAG** (Retrieval-Augmented Generation) module ingests RFP documents into a local ChromaDB vector store, retrieves relevant context for user queries, and generates answers using a local Ollama LLM — all without any cloud dependency.

## 🗂️ Architecture

Sentinel uses a local-only RAG pipeline:

1. **Ingest**: PDF or plain-text documents → text extraction → chunking → ChromaDB storage
2. **Query**: User query → ChromaDB similarity search → context retrieval → Ollama generation

### Communication

The sidecar communicates with the Tauri Rust backend via **JSON-RPC 2.0 over stdin/stdout**.

---

## 🚀 File Structure

```
sidecars/rag/
├── src_py/
│   ├── server.py              # JSON-RPC IPC dispatcher (ingest / query handlers)
│   ├── events.py              # Unified event emission for IPC (progress, results, errors)
│   ├── ingest.py               # Document ingestion: PDF/text parsing, chunking, ChromaDB storage
│   ├── ollama_client.py        # Async Ollama API client (health, models, generation)
│   ├── chroma_client.py        # Async ChromaDB embedded client (collections, query, upsert)
│   ├── utils.py                # Shared utilities (Docker loopback resolution)
├── tests/
│   ├── test_events.py          # Event system unit tests
│   ├── test_utils.py           # Utils unit tests
│   ├── test_ingest.py          # Chunking and text extraction tests
│   ├── test_server.py          # Server helper function tests
├── pyproject.toml              # Python package config
├── requirements.txt            # Python dependencies
├── pytest.ini                  # Test runner config
```

---

## 🛠️ Setup

Install the sidecar dependencies from the repository root:

```bash
pip install -e ./sidecars/rag
```

### Prerequisites

- **Python 3.11+**
- **Ollama** running on `http://localhost:11434` with at least one pulled model
- **ChromaDB** (embedded — no separate server required)
- **pypdf** (for PDF text extraction)

---

## 🔌 JSON-RPC Protocol

### Methods

| Method | Parameters | Description |
|--------|------------|-------------|
| `ingest` | `document_id`, `content` | Ingest a document into ChromaDB |
| `query` | `query` | Query the RAG pipeline with a question |

### Events (stdout, read by Tauri backend)

| Event | Data | Description |
|-------|------|-------------|
| `progress` | `{portalId, message}` | Pipeline stage update |
| `result` | `{answer, source_documents}` | Query result |
| `error` | `{message}` | Error information |
| `warning` | `{message}` | Warning information |

---

## 🧪 Testing

```bash
cd sidecars/rag
pytest tests/ -v
```

---

## 🔄 Event Flow

```
Rust Backend               Python Sidecar
───── stdin ─────►  JSON-RPC request
                    │
                    ├── ingest: PDF parsing → chunking → ChromaDB upsert
                    │   └── stdout: progress events
                    │
                    ├── query: ChromaDB search → Ollama generation
                    │   └── stdout: progress → result
                    │
◄─── stdout ──────  JSON-RPC response
```
