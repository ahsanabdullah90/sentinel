# Module: Worker Sidecar

## Purpose
The Worker sidecar handles asynchronous background job execution. Instead of relying on a resource-heavy Redis queue, it uses a lightweight local SQLite database queue (`worker_jobs.db`). It processes background scrapes, proposal draft expansions, and heavy vector ingestion asynchronously, reporting status back to the main Tauri process.

## Language & Runtime
- **Language**: Python 3.11
- **Key Libraries**:
  - `sqlite3`: Thread-safe transactional queue interface.
  - `pydantic`: Payload schema enforcement.
- **Entry point**: `sidecars/worker/src_py/worker.py`

## IPC Interface (Standard I/O JSON-RPC 2.0)
Communicates with the Tauri host process using standard stdin/stdout stream pipes.
- **Methods Received**:
  - `process_job`: Signals the worker to lock a specific job ID in the SQLite database, retrieve parameters, perform processing (e.g. scrape or indexing), and mark the job as completed or failed.
- **Events Emitted**:
  - `job_started`: Emitted when parsing begins.
  - `job_progress`: Progress updates emitted for step-by-step visual display.
  - `job_completed` / `job_failed`: Status indicators containing final output or error stack.

## Internal Structure
- `worker.py`: Manages standard I/O listener loop and coordinates the background polling/execution thread.
- `process_job`: Main execution function with signature `async def process_job(job_id: int, job_data: dict)`. It reads tasks directly from the shared `worker_jobs.db` SQLite store.

## SQLite Job Queue Schema (`worker_jobs.db`)
Stores active worker states locally:
- **`jobs`**: `id` (INTEGER PRIMARY KEY), `status` (PENDING, RUNNING, COMPLETED, FAILED), `payload` (JSON text), `result` (JSON text), `created_at`, `updated_at`.
