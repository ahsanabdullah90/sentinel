# Sentinel RFP Agent - System Architecture

## Module Inventory

| Module | Language | Port | Responsibility |
|--------|----------|------|----------------|
| Frontend | TS / React | - | User Interface & Orchestration |
| Tauri Shell | Rust | - | Desktop Shell, Persistence, gRPC Client |
| Hunter Sidecar | Python | 50051 | RFP Web Scraping & Portal Detection |
| RAG Sidecar | Python | 50052 | Semantic Search, Document Ingestion, LLM Analysis |
| Worker Sidecar | Python | 50053 | Async Background Job Processing (Redis) |
| Gap Engine | Python | 50054 | Compliance Gap & Risk Analysis |

## System Data-Flow

```text
[ User ]
   |
   v
[ Frontend (React/Vite) ] <---(Events)---+
   |                                     |
(IPC / Tauri Invoke)                     |
   |                                     |
   v                                     |
[ Tauri Shell (Rust) ]                   |
   |                                     |
   +---(SQLite: sentinel.db)             |
   |                                     |
   +---(gRPC / localhost)                |
   |      |                              |
   |      +--> [ Hunter Sidecar ] -------+
   |      |      |
   |      |      +--> [ Web Portals ]
   |      |
   |      +--> [ RAG Sidecar ] ----------+
   |      |      |
   |      |      +--> [ ChromaDB ]
   |      |      +--> [ Ollama (LLM) ]
   |      |
   |      +--> [ Worker Sidecar ] -------+
   |      |      |
   |      |      +--> [ Redis ]
   |      |
   |      +--> [ Gap Engine ] -----------+
   |
(Distributed Tracing)
   |
   v
[ Jaeger ]
```

## Proto File Index

| Proto File | Used By (Client/Caller) | Used By (Server/Implementer) |
|------------|-------------------------|------------------------------|
| `hunter.proto` | Tauri Shell | Hunter Sidecar |
| `rag.proto` | Tauri Shell | RAG Sidecar |
| `worker.proto` | Tauri Shell | Worker Sidecar |
| `gap_engine.proto` | Tauri Shell | Gap Engine Sidecar |
| `health.proto` | Tauri Shell (Bootstrap) | All Sidecars |

## Shared Resources

| Resource | Primary Owner | Read By | Written By |
|----------|---------------|---------|------------|
| SQLite (`sentinel.db`) | Tauri Shell | Tauri Shell | Tauri Shell |
| ChromaDB | RAG Sidecar | RAG Sidecar | RAG Sidecar |
| Redis | Worker Sidecar | Worker Sidecar | Worker Sidecar |
| Ollama | External | RAG, Hunter | - |
| Jaeger | External | All Modules | All Modules |
