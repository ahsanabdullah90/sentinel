# Phase 6 — Enterprise Refactor & Infrastructure

**Status:** Complete
**Started:** 2026-05-17 **Completed:** 2026-05-17

## Files Created / Modified

| File                          | Change                                                                                   |
| ----------------------------- | ---------------------------------------------------------------------------------------- |
| `docker-compose.yml`          | Created — Orchestrates sidecars (Hunter, RAG), Ollama, ChromaDB, and Redis               |
| `config/schema.ts`            | Created — Centralized Zod schema for environment variables                               |
| `config/config.yaml`          | Created — Rust backend configuration file                                                |
| `sidecars/*/package.json`     | Modified — Added dependencies for `@opentelemetry` (API, SDK, Prometheus exporter)       |
| `sidecars/*/src/telemetry.ts` | Created — Configures OpenTelemetry and Prometheus exporting on ports 9464/9465           |
| `src-tauri/Cargo.toml`        | Modified — Added `opentelemetry`, `tracing-opentelemetry`                                |
| `src-tauri/src/telemetry.rs`  | Created — Initializes Rust tracing via OpenTelemetry                                     |
| `src-tauri/tauri.conf.json`   | Modified — Hardened CSP to block external AI endpoints; added auto-updater configuration |
| `.github/workflows/ci.yml`    | Created — Sets up automated CI pipeline for tests and builds                             |
| `__tests__/*.test.ts`         | Created — Added initial integration tests for Hunter and RAG sidecars                    |
| `sidecars/worker/*`           | Created — Initial worker pool scaffold using Redis (`BLPOP`)                             |
| `sidecars/dispatcher/*`       | Created — Script to push jobs to the Redis queue                                         |
| `README.md`                   | Modified — Updated instructions for the new containerized architecture                   |

## Decisions Made

- Chose `docker-compose` as the standard runtime orchestration for sidecars to simplify dependencies on the host machine.
- Moved away from external LLM API endpoints (`generativelanguage.googleapis.com`) in the CSP to strictly enforce the "Privacy-First" local processing requirement.
- Added Redis for the worker pool to decouple long-running Playwright scrapers from the main gRPC request/response cycle.
- Opted for Prometheus exporters directly in the sidecars for immediate observability.

## Deviations from Plan

- Added integration testing stubs (`__tests__`) early to ensure the proto definitions and clients could be instantiated without needing the full system online.

## Next Phase Dependencies

- N/A. Sprint 1 + Enterprise Refactoring is complete.
