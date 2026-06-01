# Module: Hunter Sidecar

## Purpose
The Hunter sidecar is responsible for automated web scraping and RFP portal detection. It identifies search inputs, pagination elements, and portal layouts, scraping RFP details and streaming progress updates back to the Tauri shell.

## Language & Runtime
- **Language**: Python 3.11
- **Automation Framework**: Playwright (Headless Browser)
- **Key Libraries**:
  - `playwright`: Dynamic browser interaction and web scraping.
  - `pydantic`: Type-safe configuration and data structure parsing.
  - `httpx`: Lightweight asynchronous HTTP requests for static page detection.
- **Entry point**: `sidecars/hunter/src_py/server.py`

## IPC Interface (Standard I/O JSON-RPC 2.0)
The Hunter sidecar communicates purely via standard input (`stdin`) and standard output (`stdout`) stream pipes, redirecting standard output logs to `stderr` to maintain control channel purity.
- **Methods Received**:
  - `detect_portal`: Analyzes a URL's markup to determine the portal structure (auth method, login elements).
  - `start_hunt`: Spawns the web scraper to crawl opportunities based on search keywords.
- **Events Emitted**:
  - `portal_detected`: Emits a structured detection report (e.g. login selectors, API endpoints).
  - `opportunity_found`: Streams details of an identified RFP (title, link, description, release date).
  - `progress`: Regular visual logs sent to the frontend dashboard.
  - `error`: Formatted error messages if a page fails to load or authentication fails.

## Internal Structure
- `server.py`: Listens to `stdin` JSON-RPC requests and dispatches tasks asynchronously.
- `scraper_engine.py`: Manages browser automation, page navigation, and DOM query selectors.
- `portal_analyzer.py`: Checks URL headings and markers to auto-detect the portal category.
- `portal_runner.py`: Controls execution loop for scraping jobs.
- `rate_limiter.py`: Implements a secure token-bucket rate limiter with exponential back-off and captcha handling.
- `models.py`: Defines data schemas for portal presets and opportunities.
- `adapters/`: Generic fallback scraper and custom site-specific scrapers (e.g. BrightSpyre).

## Startup Sequence
1. The Tauri Rust Shell spawns the Python sidecar as a child process.
2. The sidecar starts a standard asyncio loop reading from `sys.stdin`.
3. Standard output (`sys.stdout`) is captured and redirected to `sys.stderr` for logs, preserving standard output exclusively for pure JSON-RPC payloads.
4. Spawns headless Playwright browser contexts dynamically upon requests.
