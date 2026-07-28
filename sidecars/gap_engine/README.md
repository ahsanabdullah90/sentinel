# Gap Engine Sidecar — Compliance Gap Analysis

The **Gap Engine** analyzes RFP documents for compliance gaps, missing requirements, and risks using a local Ollama LLM.

## 🗂️ Architecture

### Data Flow
1. **Context Retrieval**: Queries ChromaDB for RFP document chunks
2. **Zero-Shot Analysis**: Sends document context to Ollama with an auditing prompt
3. **Response Parsing**: Validates and structures the LLM response into gap items
4. **Fallback**: Returns generic warnings if inference fails (keeps tests green)

### Communication

The sidecar communicates with the Tauri Rust backend via **JSON-RPC 2.0 over stdin/stdout**.

---

## 🚀 File Structure

```
sidecars/gap_engine/
├── src_py/
│   ├── server.py              # JSON-RPC IPC dispatcher (analyze_gaps method)
│   ├── events.py              # Unified event emission for IPC
│   ├── gap_analyzer.py        # Core gap analysis orchestration
│   ├── chroma_utils.py        # ChromaDB query abstraction
│   ├── ollama_utils.py        # Ollama prompt building and response parsing
│   ├── gap_engine.py           # Backward-compatible import hub
├── tests/
│   ├── test_events.py         # Event system unit tests
│   ├── test_ollama_utils.py   # Ollama response parsing tests
│   ├── test_chroma_utils.py   # ChromaDB query tests
├── conftest.py                # Project root path setup
├── pytest.ini                 # Test runner config
├── pyproject.toml             # Python package config
└── README.md
```

---

## 🛠️ Setup

```bash
pip install -e ./sidecars/gap-engine
pip install -e ".[test]"  # optional: test dependencies
```

### Prerequisites

- **Python 3.11+**
- **Ollama** running on `http://localhost:11434`
- **ChromaDB** (shared with RAG sidecar)

---

## 🔌 JSON-RPC Protocol

### Methods

| Method | Parameters | Description |
|--------|------------|-------------|
| `analyze_gaps` | `rfp_id`, `ollama_url`, `ollama_model` | Analyze RFP for compliance gaps |

### Events (stdout, read by Tauri backend)

| Event | Data | Description |
|-------|------|-------------|
| `progress` | `{portalId, message}` | Analysis stage update |
| `gap_report_generated` | `{rfpId, gaps}` | Complete gap report |
| `result` | `{rfp_id, gaps}` | JSON-RPC response |
| `error` | `{message}` | Error information |
| `ready` | `{}` | Server ready signal |

---

## 🧪 Testing

```bash
cd sidecars/gap-engine
pytest tests/ -v
```
