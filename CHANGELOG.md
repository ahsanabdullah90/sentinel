# Changelog

All notable changes to the Sentinel project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.0.0] - 2026-05-25

### Added

- **Python Backend Sidecars**: Migrated Hunter and RAG sidecars from TypeScript to Python 3.11 with full async/await support.
- **Hunter Sidecar** (`sidecars/hunter/src_py/`):
  - `rate_limiter.py` – Token-bucket rate limiter with secure jitter, exponential back-off, and CAPTCHA pause.
  - `scraper_engine.py` – Strategy pattern for scraping (PublicAPI, StaticHTML, Playwright, GenericSearch with Gemini AI).
  - `portal_analyzer.py` – AI-powered portal detection using Gemini with heuristic fallback.
  - `portal_runner.py` – Orchestrates per-portal scraping pipelines.
  - `server.py` – gRPC server hosting `Detect` and `Hunt` RPCs.
- **RAG Sidecar** (`sidecars/rag/src_py/`):
  - `chroma_client.py` – Async HTTP wrapper for ChromaDB REST API.
  - `ollama_client.py` – Async HTTP wrapper for Ollama generation API.
  - `ingest.py` – Document ingestion pipeline (text extraction, chunking, embedding storage).
  - `server.py` – gRPC server hosting `Ingest` and `Query` RPCs.
- **Gap Engine** (`sidecars/gap-engine/src_py/`):
  - `gap_engine.py` – RFP gap analysis with structured JSON output.
- **Worker Sidecar** (`sidecars/worker/src_py/`):
  - `worker.py` – Redis-backed background job processor with concrete data transformation:
    - Text normalisation, content hashing for deduplication, metadata enrichment.
    - gRPC `EnqueueJob` RPC for submitting jobs.
  - `worker.proto` – Protobuf service definition with generated `_pb2` stubs.
- **Architecture Documentation** (`docs/architecture.md`):
  - Component table, Mermaid architecture diagram, data-flow description.
- **Pytest Test Suite** (`tests/`):
  - `test_rate_limiter.py` – 13 unit tests for token bucket behaviour.
  - `test_scraper_engine.py` – JSON extraction and strategy factory tests.
  - `test_gap_engine.py` – Gap analysis output validation.
  - `test_worker.py` – Job processing, validation, normalisation, and hashing tests.
  - `test_hunter_grpc.py` – End-to-end gRPC integration tests for Hunter.
  - `test_rag_grpc.py` – End-to-end gRPC integration tests for RAG.
- **Comprehensive Docstrings**: Module-level and function-level docstrings added to all Python modules.

### Changed

- Version bumped from `0.1.0` to `1.0.0` reflecting the completed Python backend migration.
- Refactored duplicated search-input detection logic in `scraper_engine.py` into a reusable `_detect_search_input` static method.
- Simplified model-selection fallback loop in `rag/server.py`.

### Fixed

- Removed duplicate import blocks that were introduced during incremental docstring additions.
- Fixed `audit_report.py` path resolution bug that caused `ValueError` on `relative_to()`.

## [0.1.0] - 2026-05-24

### Added

- Initial project scaffold with Tauri + React frontend.
- TypeScript-based Hunter and RAG sidecar stubs.
- gRPC protobuf definitions for Hunter and RAG services.
- Vitest integration test suite.
- Docker Compose configuration for multi-sidecar development.
