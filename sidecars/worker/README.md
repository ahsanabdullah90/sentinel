# Worker Sidecar — SQLite-Backed Background Job Processor

The **Worker** module provides a persistent background job queue backed by a local SQLite database. Jobs are processed asynchronously with deduplication via SHA-256 content hashing.

## 🗂️ Architecture

### Data Flow
1. **Enqueue**: JSON-RPC `enqueue_job` → SQLite `jobs` table (status: `pending`)
2. **Process**: Worker loop polls for `pending` → marks `processing` → runs job logic → saves result (`completed` / `failed`)
3. **Recovery**: On startup, stuck `processing` jobs are reset to `pending`
4. **Retention**: Completed/failed jobs older than 7 days are pruned automatically

### Communication

The sidecar communicates with the Tauri Rust backend via **JSON-RPC 2.0 over stdin/stdout**.

---

## 🚀 File Structure

```
sidecars/worker/
├── src_py/
│   ├── server.py              # JSON-RPC IPC dispatcher + worker polling loop
│   ├── events.py              # Unified event emission for IPC
│   ├── db.py                  # SQLite database operations (init, enqueue, pop, save)
│   ├── jobs.py                # Business logic: normalization, hashing, result formatting
├── tests/
│   ├── test_events.py         # Event system unit tests
│   ├── test_db.py             # Database operation tests
│   ├── test_jobs.py           # Job processing logic tests
├── pyproject.toml             # Python package config
├── requirements.txt           # Python dependencies (none — stdlib only)
├── pytest.ini                 # Test runner config
└── README.md                  # This file
```

---

## 🛠️ Setup

Install the sidecar dependencies from the repository root:

```bash
pip install -e ./sidecars/worker
```

### Prerequisites

- **Python 3.11+**
- No external dependencies (stdlib: sqlite3, hashlib, json)

---

## 🔌 JSON-RPC Protocol

### Methods

| Method | Parameters | Description |
|--------|------------|-------------|
| `enqueue_job` | `rfp_id`, `payload` | Enqueue a new background job |

### Events (stdout, read by Tauri backend)

| Event | Data | Description |
|-------|------|-------------|
| `progress` | `{portalId, message}` | Worker status update |
| `ready` | `{}` | Server ready signal |
| `result` | `{success, message}` | Job enqueue result |
| `error` | `{message}` | Error information |

---

## 🧪 Testing

```bash
cd sidecars/worker
pytest tests/ -v
```

### Running root-level tests

```bash
cd /
pytest tests/test_worker.py -v
```
