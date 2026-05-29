# Phase 8 — Hunter Scraper Python Refactoring & gRPC Streaming

**Status:** Complete
**Started:** 2026-05-29 **Completed:** 2026-05-29

## Files Created / Modified

| File | Change |
| --- | --- |
| `sidecars/hunter/src_py/models.py` | Created — Strict Pydantic models for incoming configs and outgoing opportunities |
| `sidecars/hunter/src_py/utils/search_detector.py` | Created — Extracted heuristic visual search input JS locator |
| `sidecars/hunter/src_py/adapters/` | Created — Pluggable extraction interface with specific Brightspyre and Generic adapters |
| `sidecars/hunter/src_py/scraper_engine.py` | Modified — Integrated pluggable adapters, dynamic local Ollama model extraction, and `ProgressReporter` |
| `sidecars/hunter/src_py/portal_analyzer.py` | Modified — Replaced Gemini with local Ollama visual parsing heuristics |
| `sidecars/hunter/src_py/server.py` | Modified — Async gRPC server supporting multi-client streams and active task cancellation |
| `src-tauri/src/sidecar.rs` | Modified — Built Rust gRPC auto-launcher, process manager, and Tauri event mapping |
| `src-tauri/src/commands/hunting.rs` | Modified — Hooked `start_hunt_session` and `stop_hunt_session` to Tonic streams |
| `docs/master.md` | Modified — Updated sidecar protocols and guidelines to cover Tonic gRPC streams |
| `docs/agent-context.md` | Modified — Corrected Hunter dependencies (Python, pip packages, Playwright installation) |
| `sidecars/hunter/README.md` | Created — Definitive architectural overview of the Python gRPC Scraper module |

## Decisions Made

* **Python over TypeScript**: Unified all scraping logic into Python `asyncio` to reduce duplicate maintenance overhead and take advantage of standard Python data science and scraping tools.
* **Tonic gRPC Streaming**: Used Tonic gRPC over JSON-lines for the Hunter sidecar to allow real-time structured telemetry streams and robust async cancellations.
* **TCP Port Auto-Detection**: Implemented TcpStream polling in Rust to verify port `50051` health, launching the server subprocess automatically if inactive.
* **No-Cloud Ollama Fallback**: Replaced Gemini SDK with direct, fast querying of local Ollama models (`/api/tags`), querying dynamically for whatever is installed on the host machine.
* **gRPC Disconnect Cancellation**: Configured Python to catch gRPC streaming client disconnections, letting it clean up browser contexts instantly and prevent leaked chromium threads.

## Deviations from Plan

* None.

## Test Results

* Verified Rust backend compiles flawlessly without errors or warnings.
* Python server tested operational under port checking logic.

## Next Phase Dependencies

* None. Refactoring and documentation are fully in order.
