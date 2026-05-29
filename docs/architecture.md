# Sentinel Architecture Overview

This document provides a visual and textual overview of the **Sentinel** system after the migration of the backend sidecars to Python.

---

## System Components

| Component          | Language                             | Description                                                                               |
| ------------------ | ------------------------------------ | ----------------------------------------------------------------------------------------- |
| **Frontend**       | TypeScript (Tauri + React)           | Desktop UI that interacts with the backend.                                               |
| **Hunter Sidecar** | Python (asyncio, Playwright, Gemini) | Handles portal detection, scraping strategies, and rate‑limiting.                         |
| **RAG Sidecar**    | Python (Ollama, ChromaDB)            | Ingests documents, stores embeddings, and answers queries.                                |
| **Gap Engine**     | Python (CLI & stdout capture)        | Fully integrated RFP gap analyzer with JSON event reporting.                              |
| **Worker**         | Python (redis‑py, gRPC)              | Fully integrated background job processor that consumes tasks from Redis queues.          |
| **gRPC Protobuf**  | `.proto` files                       | Defines the service contracts between the frontend, hunter, rag, and worker sidecars.     |
| **Docker Compose** | Docker                               | Orchestrates containers for each sidecar and supporting services (Redis, Chroma, Ollama). |

---

## Architecture Diagram

```mermaid
flowchart TD
    subgraph Frontend[Frontend (TS/Tauri)]
        FE[React UI]
    end

    subgraph Hunter[Hunter Sidecar (Python)]
        HL[RateLimiter]
        HS[ScraperEngine]
        HA[PortalAnalyzer]
    end

    subgraph RAG[RAG Sidecar (Python)]
        RI[Ingest]
        RQ[Query]
        RC[ChromaClient]
        RO[OllamaClient]
    end

    subgraph Gap[Gap Engine (Python)]
        GE[Gap Analyzer]
    end

    subgraph Worker[Worker (Python)]
        WK[Redis Worker]
    end

    FE -->|gRPC Detect| HL
    FE -->|gRPC Hunt| HS
    FE -->|gRPC Ingest| RI
    FE -->|gRPC Query| RQ
    FE -->|gRPC AnalyzeGaps| GE
    FE -->|gRPC ProcessJob| WK

    HL --> HS
    HS --> HA
    HA -->|detects search selector| HS

    RI --> RC
    RI --> RO
    RQ --> RC
    RQ --> RO

    style Frontend fill:#f9f9f9,stroke:#333,stroke-width:2px
    style Hunter fill:#e3f2fd,stroke:#1565c0,stroke-width:2px
    style RAG fill:#e8f5e9,stroke:#2e7d32,stroke-width:2px
    style Gap fill:#fff3e0,stroke:#ef6c00,stroke-width:2px
    style Worker fill:#fce4ec,stroke:#c2185b,stroke-width:2px
```

---

## Data Flow

1. **User initiates a hunt** → Frontend calls `Hunter.Detect` → `PortalAnalyzer` identifies the search selector → `ScraperEngine` performs the search and streams back opportunities.
2. **User submits a document** → Frontend calls `RAG.Ingest` → `Ingest` stores the document, creates embeddings via `OllamaClient`, and upserts into `ChromaClient`.
3. **User asks a question** → Frontend calls `RAG.Query` → Context is retrieved from ChromaDB, fed to Ollama to generate an answer.
4. **Gap analysis** → Frontend calls `GapEngine.analyzeGaps` → Returns a structured gap report.
5. **Background jobs** → Frontend enqueues a job to Redis → `Worker` continuously polls and processes the job.

---

## System Status

All core components described in the architecture documents, including the **Worker** and **Gap Engine** services, are fully integrated into the Docker compose orchestration. The native Rust database query optimization (EXISTS) and the secure bootstrapping sequence are fully completed and validated.

---

_Updated on 2026‑05‑29._
