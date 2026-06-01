# Module: RAG Sidecar

## Purpose
The RAG (Retrieval-Augmented Generation) sidecar manages the storage and retrieval of RFP documents and knowledge base items. It uses ChromaDB as a vector database for semantic search and interacts with local Ollama instances for text generation and analysis.

## Language & Runtime
- **Language**: Python 3.11
- **Framework**: gRPC (asyncio)
- **Key Libraries**: chromadb, grpcio, opentelemetry
- **Entry point**: `sidecars/rag/src_py/server.py`

## Public Interface
### gRPC Service: `RagService`
- `Ingest(IngestRequest) returns (IngestResponse)`: Processes a document, chunks it, and stores it in ChromaDB.
- `Query(QueryRequest) returns (QueryResponse)`: Performs semantic search and generates an answer using an LLM.

## Internal Structure
- `server.py`: gRPC server and service handlers.
- `chroma_client.py`: Wrapper around ChromaDB REST API for collection management and upsert/query operations.
- `ollama_client.py`: Wrapper around Ollama REST API for health checks and text generation.
- `ingest.py`: Document processing pipeline (text extraction, chunking, and storage).

## Dependencies
### Internal
| Module | How consumed |
|--------|-------------|
| Proto Contracts | Python stubs generated from `rag.proto` |

### External
| Package | Version | Purpose |
|---------|---------|---------|
| chromadb | 0.5.0 | Vector database |
| grpcio | 1.62.1 | gRPC runtime |
| ollama | (External) | LLM service |

## Configuration
| Variable | Required | Default | Crash if missing? |
|----------|----------|---------|-------------------|
| PORT | No | 50052 | No |
| CHROMA_URL | Yes | http://localhost:8000 | No (handled in client) |
| CHROMA_AUTH_TOKEN| Yes (prod) | - | No |
| OLLAMA_URL | Yes | http://localhost:11434 | No |

## Data Flow
- **Ingestion**: File Path -> `ingest_document` -> Text Extraction -> Chunking -> `ChromaClient` -> ChromaDB.
- **Query**: Question -> `ChromaClient` (Search) -> Context -> `OllamaClient` (Generate) -> Answer.

## Startup Sequence
1. Telemetry and logging initialization.
2. gRPC server setup with tracing and optional auth interceptors.
3. Server starts on port 50052.
