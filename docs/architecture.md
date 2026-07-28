# Sentinel Architecture Overview

This document provides an accurate, up-to-date visual and textual overview of the **Sentinel** system. The architecture uses a secure local IPC stream pattern based on **JSON-RPC 2.0** over standard input/output (stdin/stdout), eliminating local network port binding, gRPC, and Redis dependencies.

---

## System Components

| Component          | Technology Stack                     | Communication / Role                                                                          |
| ------------------ | ------------------------------------ | --------------------------------------------------------------------------------------------- |
| **Frontend UI**    | React, TypeScript, Lucide, Tailwind  | Desktop application user interface; communicates with the Tauri core using native IPC.       |
| **Tauri Core**     | Rust (`src-tauri`)                   | Launches and monitors Python sidecars as subprocesses; manages process lifecycle, Mutex locks, and `sentinel.db` SQLite storage. |
| **Hunter Sidecar** | Python (Playwright, Ollama)          | Identifies search selectors on target websites, runs scrapers, and streams back matching RFPs. |
| **RAG Sidecar**    | Python (ChromaDB, Ollama)            | Ingests compliance documents, generates vector embeddings, and executes semantic queries.     |
| **Gap Engine**     | Python                               | Compliance gap analyzer that parses RFP opportunities to identify structural requirements.    |
| **Worker Sidecar** | Python (SQLite Queue, `worker_jobs.db`) | Performs background tasks asynchronously, polling a local SQLite job queue database.          |

---

## Architecture Diagram

```mermaid
flowchart TD
    subgraph UI[Frontend (React / TypeScript)]
        React[React Views]
    end

    subgraph Tauri[Tauri Desktop Core (Rust)]
        ProcessMgr[Process Manager]
        MutexLock[Mutex / Process Handles]
        SQLite[Local SQLite: sentinel.db]
    end

    subgraph Python[Python Sidecars (Subprocesses)]
        subgraph Hunter[Hunter Sidecar]
            Scraper[Scraper Engine]
            Playwright[Playwright Web automation]
        end

        subgraph RAG[RAG Sidecar]
            Chroma[ChromaDB Client]
            Ollama[Ollama LLM Client]
        end

        subgraph Gap[Gap Engine]
            GapAnalyzer[Gap Analyzer]
        end

        subgraph Worker[Worker Sidecar]
            SQLiteQueue[SQLite Job Queue: worker_jobs.db]
        end
    end

    React -->|Tauri Invoke| ProcessMgr
    ProcessMgr -->|Mutex Lock Safety| MutexLock
    ProcessMgr -->|Read/Write State| SQLite

    %% Standard I/O stream JSON-RPC 2.0 Connections
    ProcessMgr <-->|JSON-RPC 2.0 over stdin/stdout| Hunter
    ProcessMgr <-->|JSON-RPC 2.0 over stdin/stdout| RAG
    ProcessMgr <-->|JSON-RPC 2.0 over stdin/stdout| Gap
    ProcessMgr <-->|JSON-RPC 2.0 over stdin/stdout| Worker

    Scraper --> Playwright
    RAG --> Chroma
    RAG --> Ollama
    Worker --> SQLiteQueue

    style UI fill:#f5f5f7,stroke:#1d1d1f,stroke-width:2px
    style Tauri fill:#e8f4fc,stroke:#0071e3,stroke-width:2px
    style Python fill:#f4fbfc,stroke:#008080,stroke-width:2px
    style Hunter fill:#fff9db,stroke:#fab005,stroke-width:1px
    style RAG fill:#ebfbee,stroke:#40c057,stroke-width:1px
    style Gap fill:#fff4e6,stroke:#fd7e14,stroke-width:1px
    style Worker fill:#fff0f6,stroke:#e64980,stroke-width:1px
```

---

## Key Architectural Principles

### 1. Zero Network Binding (High Security)
Unlike traditional architectures that run sidecars on local HTTP or gRPC TCP ports (e.g., `localhost:50051`), Sentinel communicates entirely using standard input (`stdin`) and standard output (`stdout`) pipes. This completely prevents:
- Port conflict crashes on user machines.
- Firewalls blockages.
- Local network snooping or cross-site scripting hijacks of backend engines.

### 2. JSON-RPC 2.0 Protocol Standard
All standard I/O messages are wrapped in standard compliant JSON-RPC 2.0 structures:
```json
{
  "jsonrpc": "2.0",
  "method": "detect_portal",
  "params": { "url": "https://example-rfp.com" },
  "id": 1
}
```
Replies are returned asynchronously via stdout streams. All debug and execution logs are routed directly through `stderr` to avoid polluting the JSON control channel.

### 3. SQLite-Backed Persistent Queue
To prevent bloating with heavy third-party cache servers:
- Background tasks are enqueued into a light, transaction-safe SQLite database (`worker_jobs.db`).
- The **Worker Sidecar** polls this queue locally and writes progress updates without requiring a Redis daemon.

### 4. Thread-Safe Mutex Recovery
The Rust process manager uses robust Mutex locks to synchronize command triggers. If a thread panics while holding a process handle, locks are recovered safely via `lock().unwrap_or_else(|poisoned| poisoned.into_inner())` rather than causing application-wide freezes.

---

### 5. RAG Sidecar Module Architecture

The RAG sidecar provides local retrieval-augmented generation using ChromaDB and Ollama.

| Module | Responsibility |
|------|------|
| `server.py` | JSON-RPC IPC dispatcher; handles ingest and query methods |
| `events.py` | Unified event emission for IPC progress, results, and errors |
| `ingest.py` | Document ingestion pipeline (PDF/text parsing, chunking, ChromaDB storage) |
| `ollama_client.py` | Async Ollama API client with Docker loopback resolution |
| `chroma_client.py` | Async ChromaDB embedded client with lazy initialization |
| `utils.py` | Shared utilities (Docker loopback resolution) |

All IPC events flow through `events.py` which captures the original stdout before redirection, ensuring JSON-RPC protocol integrity.

### 7. Worker Sidecar Module Architecture

The Worker sidecar provides a SQLite-backed background job processor with content-hash deduplication.

| Module | Responsibility |
|------|------|
| `server.py` | JSON-RPC IPC dispatcher + worker polling loop; manages async task lifecycle |
| `events.py` | Unified event emission for IPC (progress, ready, results, errors) |
| `db.py` | SQLite database operations (schema init, enqueue, pop, save result) with WAL journaling |
| `jobs.py` | Business logic: input normalization, SHA-256 content hashing, result formatting |

The worker loop runs as a concurrent asyncio task alongside the JSON-RPC dispatcher, polling the SQLite queue every second. Stuck `processing` jobs are recovered to `pending` on startup, and completed/failed jobs older than 7 days are automatically pruned.

### 6. Gap Engine Sidecar Module Architecture

The Gap Engine analyzes RFP documents for compliance gaps using ChromaDB context and Ollama inference.

| Module | Responsibility |
|------|------|
| `server.py` | JSON-RPC IPC dispatcher; handles `analyze_gaps` method |
| `events.py` | Unified event emission for IPC (progress, gap reports, results, errors) |
| `gap_analyzer.py` | Core orchestration: ChromaDB context retrieval → Ollama inference → event emission |
| `chroma_utils.py` | ChromaDB query abstraction (decoupled from RAG internals) |
| `ollama_utils.py` | Zero-shot auditing prompt builder + response parser with JSON validation |
| `gap_engine.py` | Backward-compatible import hub (re-exports `analyze_gaps`) |

All gap reports are emitted via `events.emit_gap_report()` and fall back to generic warnings when Ollama inference fails.

### 8. Hunter Sidecar Module Architecture

The Hunter sidecar has been refactored into focused sub-modules for maintainability:

| Module                  | Responsibility                                                |
| ----------------------- | ------------------------------------------------------------- |
| `server.py`             | JSON-RPC IPC dispatcher; stdin → async task routing           |
| `progress_reporter.py`  | Structured event reporting (progress, opportunities, errors)  |
| `ollama_utils.py`       | Synchronous Ollama HTTP helpers + JSON extraction             |
| `strategies.py`         | Scraping strategy pattern + `get_strategy()` factory          |
| `portal_runner.py`      | Per-portal orchestration with rate-limiter lifecycle          |
| `portal_analyzer.py`    | Portal URL analysis (search bar detection)                    |
| `rate_limiter.py`       | Token-bucket rate limiting with CAPTCHA pause                |
| `models.py`             | Pydantic schemas for config and scraped data                  |
| `scraper_engine.py`     | Backward-compatible import hub (re-exports all public API)    |

All existing import paths (`from ...scraper_engine import ...`) continue to work via the re-export hub.

---

_Updated on 2026-07-29._
