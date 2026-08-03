# Changelog

All notable changes to the Sentinel project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.4.1] - 2026-08-02

### Fixed

- **Gemini model listing filter**: The model-list parser checked for `":generateContent"` but the Google API returns plain `["generateContent"]`, which filtered out every model and made provider health checks always fail. Now correctly matches generation-capable models.
- **Free-tier model defaults**: `gemini-2.5-flash` is retired for new (free-tier) keys, and `text-embedding-004` is unavailable. Defaults changed to **`gemini-flash-latest`** (generation) and **`gemini-embedding-001`** (RAG embeddings) across the shared client, frontend, and `.env.example`.
- **Automatic model fallback**: If the configured Gemini model returns HTTP 404 (retired) or 429 (quota), generation now falls back through `gemini-flash-latest` → `gemini-3.1-flash-lite` → `gemini-3.5-flash` instead of failing.
- **AI provider label**: Dashboard status pill now reads "AI: ..." instead of "Ollama: ...".

### Changed

- Settings modal auto-opens on boot when no provider is configured, prompting the user to add a Google AI Studio API key (or start Ollama).
- Portal auto-detection (`detect_portal`) now passes the active provider configuration to the hunter sidecar.

## [1.4.0] - 2026-08-02

### Added

- **Cloud-First AI Provider (Google Gemini)**: All LLM calls can now run on Google AI Studio / Gemini (`gemini-2.5-flash` default) instead of requiring a local Ollama setup. A new shared LLM client (`sidecars/shared/llm_client.py`) centralizes generation, model listing, and health checks across the hunter, RAG, and gap-engine sidecars.
- **Provider Switch in Settings**: The Settings modal now has a provider toggle — **Google Gemini** (API key + model list) or **Ollama (Local)** (URL + model). Settings are persisted in `localStorage`.
- **Automatic Provider Detection on Boot**: On startup the app probes Ollama. If online, it defaults to Ollama; otherwise it falls back to Google and, if no API key is saved, prompts the user to connect a provider in Settings.
- **Provider Gating**: Hunt sessions, add-from-link, drafting, gap analysis, and vision analysis are blocked (with a prompt to open Settings) until a provider is configured and healthy.
- **Google Embeddings for RAG**: When the provider is Google, ChromaDB uses `text-embedding-004` via a custom embedding function, making the vector store fully cloud-based. Local Ollama/ONNX embeddings remain for the Ollama path.
- **Provider-Aware Rust Commands**: `check_llm_provider`, `get_llm_models`, `generate_chat_response`, `generate_vision_description`, and `analyze_gaps` accept provider config and branch between Gemini and Ollama.
- **Softened Launcher**: `run.bat` no longer hard-requires or auto-starts Ollama; it prints a soft detection note and proceeds. `bootstrap_system` uses a quick non-fatal Ollama probe instead of a blocking 15s wait.

### Changed

- All three sidecars (hunter, rag, gap_engine) now import the shared `sidecars.shared.llm_client` instead of bespoke per-sidecar Ollama helpers.
- `PortalConfig` (hunter) gains `provider`, `googleApiKey`, `googleModel` fields, threaded through the hunt config from the frontend.

## [1.3.0] - 2026-08-02

### Added

- **Add Opportunity from Link**: The Opportunities modal now has a "Paste Link" mode. Pasting an opportunity URL and clicking "Fetch Details" invokes the new `fetch_opportunity_from_url` command, which uses the hunter sidecar (`extract_opportunity`) with Playwright + local Ollama to auto-populate title, issuing organization, deadline, and description. Fields remain editable before saving.
- **Optional Portal**: `portal_id` is now nullable (Migration 13 rebuilds the `opportunities` table). Manually added opportunities no longer require a source portal; they display under "Manual Entry" and are counted without a portal.
- **Inline Edit**: The opportunity detail view now supports editing core fields (title, issuing organization, deadline, URL, description) via an Edit button and `edit_opportunity_fields` command.
- **Migration 13**: Rebuilds the `opportunities` table to drop the restrictive `status CHECK` constraint (which blocked `applied` / `dismissed` values) and makes `portal_id` nullable. All existing columns are preserved.
- **Hunter sidecar `extract_opportunity`**: New JSON-RPC method that fetches a single opportunity URL, validates it is not a 404 / custom error page, and extracts structured details via local Ollama (prefers `qwen3` / `gemma3` models).

## [1.2.0] - 2026-08-02

### Added

- **Opportunity Priority (3-tier)**: New `priority` column (`high` / `medium` / `low` / `none`) with a per-card toggle in the Opportunities modal and a colored badge (red/amber/blue) on feed rows and the detail view. Priority sorts opportunities within each section so high-priority work is surfaced first.
- **Application Tracking**: Merged disposition into the existing `status` field (they are the same axis). New `applied` status with metadata (`applied_at`, `submission_ref`, `apply_notes`) captured through an inline "Mark as Applied" form.
- **Dismissed Lifecycle**: New `dismissed` status with a `dismiss_note`. Dismissed opportunities are greyed out and grouped at the bottom under a "Dismissed" heading. A manual "Dismiss" action sets the note to `not interested`.
- **Auto-Expiry**: `expire_not_applied` runs on app bootstrap and every time the Opportunities modal opens. Not-applied opportunities whose deadline has passed are automatically moved to `dismissed` with the note `deadline expired`. Applied opportunities are always retained.
- **Grouped Modal**: The Opportunities modal now renders opportunities under three headings — **Not Applied**, **Applied**, **Dismissed** — with within-section sorting by priority then deadline.
- **Attachment Open**: New `open_attachment` command writes stored attachment bytes to the attachments directory and opens them with the OS default application (external-link button on each attachment row).
- **DOCX Text Extraction**: Rust-side extraction of `word/document.xml` from DOCX files (via the `zip` crate) so DOCX attachments receive `extracted_text` and can be RAG-ingested alongside PDFs.
- **Real-Time Frontend Events**: Fixed the Tauri internals guard (`__TAURI_INTERNALS__`) so event listeners register and the opportunity feed updates live during hunts.
- **Correct Persisted URLs**: Opportunities are re-emitted after hybrid URL resolution so the database stores real `/jobs/<id>` URLs instead of hallucinated slugs.

### Fixed

- `update_opportunity_description` generalized to `update_opportunity_details` so the backend persists the corrected URL on `opportunity_updated`.

## [1.1.0] - 2026-07-25

### Added

- **Launch & Lifecycle Manager (`run.bat`)**: Added Windows batch launcher with automatic Ollama dependency checking and background service startup.
- **Audit & Code Review (`review-Sentinel-filelevel.md`)**: Comprehensive file-level security, maintainability, and architectural audit report.

### Changed

- **Python Sidecars**: Refactored `gap_engine`, `hunter`, and `rag` sidecars with enhanced scraping strategies, updated dependency requirements, and Chroma client error handling.
- **Tauri Integration**: Expanded Tauri database commands and main library bindings (`src-tauri/src/commands/db_commands.rs`, `src-tauri/src/lib.rs`).
- **UI Components**: Updated GapReport, KnowledgeBaseDashboard, OpportunitiesModal, OpportunityDetail, and SettingsModal UI components.

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
- **Gap Engine** (`sidecars/gap_engine/src_py/`):
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
