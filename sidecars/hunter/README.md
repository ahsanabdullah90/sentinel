# Hunter Sidecar — Unified Python Scraper Engine

The **Hunter** module is a local-only, high-performance, rate-limiting-compliant intelligence engine responsible for discovering and scraping RFP opportunities from targeted portals.

## 🚀 Key Architectural Changes

1. **Shifted from Node/TypeScript to Python**:
   - The TypeScript scraper has been completely purged to prevent logic duplication.
   - Core scraping and analysis are unified under a strict, optimized Python `asyncio` runtime.

2. **Zero Cloud-LLM Dependecy**:
   - Replaced Gemini/OpenAI completely with **local-only Ollama integration**.
   - Strict model enforcement: uses settings-configured local models or dynamically discovers the first available model installed locally inside Ollama (`/api/tags`). Hardcoded priority lists are removed.

3. **Pluggable Portal Adapters**:
   - Extensible portal extraction logic built on `BasePortalAdapter`.
   - Dedicated `BrightspyreAdapter` for custom parameter mapping and direct search payload handling.
   - Safe `GenericAdapter` fallback with browser heuristics to support any unstructured RFP search page.

4. **Robust Rust Auto-spawner & IPC**:
   - Tauri core (Rust) auto-launches the Python sidecar as a subprocess.
   - Full stream mapping: Rust converts real-time JSON-RPC stdout events into desktop Tauri frontend event emissions.

5. **Graceful Cancellations**:
   - Stopping a hunt session immediately terminates the subprocess.
   - The Rust backend manages the child process lifecycle, preventing zombie processes.

---

## 🛠️ System Requirements & Setup

Ensure the following are installed:
- **Python 3.10+**
- **Playwright** (`playwright install chromium`)
- **Ollama** (running on `http://localhost:11434`)

### Setup Script
Ensure Python dependencies are ready:
```bash
pip install playwright pydantic httpx
```

Ensure Playwright browser is ready:
```bash
playwright install chromium
```

---

## 📁 File Structure

```
sidecars/hunter/
├── src_py/
│   ├── server.py              # Async JSON-RPC over stdin/stdout
│   ├── scraper_engine.py      # Core Playwright & Ollama extraction engine
│   ├── portal_runner.py       # Orchestrator for real-time progress callbacks
│   ├── portal_analyzer.py     # Local-only schema and portal field heuristics
│   ├── models.py              # Strict Pydantic validated output schemas
│   ├── utils/
│   │   ├── search_detector.py # Centralized JS-injection heuristic search input locator
│   ├── adapters/
│   │   ├── base.py            # Base abstract portal adapter interface
│   │   ├── brightspyre.py     # Custom adapter for Brightspyre
│   │   ├── generic.py         # Standard browser-heuristic fallback adapter
├── package.json               # Simplified CLI commands
```

---

## ⚡ CLI & Test Execution

### Direct Execution
Start the server from the workspace root directory:
```bash
# Add workspace root and proto to PYTHONPATH
PYTHONPATH=. python3 sidecars/hunter/src_py/server.py
```

### Script Execution (CLI mode)
Run the CLI search directly from the workspace root directory:
```bash
PYTHONPATH=. python3 sidecars/hunter/src_py/scraper_engine.py --portal brightspyre --query "software" --limit 5
```

---

## 🔄 Protocol & Event Mapping

Events are pushed in real-time from the Python sidecar to Rust via stdout and emitted to Tauri frontend listeners:

| Python Engine Event | Rust Stream Handler | Tauri Frontend Event |
|:---|:---|:---|
| `progress` | Emits `sentinel://hunter/progress` | Displays live search log in UI |
| `opportunity_found` | Emits `sentinel://hunter/opportunity-found` | Populates opportunities dashboard |
| `portal_detected` | Emits `sentinel://hunter/portal-detected` | Populates portal configuration modal |

---

## 🛡️ Anti-Fingerprinting & Rate Limiting Guidelines

To guarantee high rate-limiting compliance, the Python engine enforces:
- Strict token bucket (15 tokens/minute, maximum burst of 5).
- Adaptive jitter (2 to 8 seconds delay randomized cryptographically between requests).
- Serial execution to prevent concurrent portal request overlap.
