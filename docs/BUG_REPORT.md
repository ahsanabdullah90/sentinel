# Bug Report - Sentinel RFP Agent

## BUG-001

**Severity:** CRITICAL
**Module:** Infrastructure
**File:** `docker-compose.yml`
**Language:** YAML

**Description:**
Hardcoded sensitive secrets are present directly in the `docker-compose.yml` file instead of being interpolated from an `.env` file.

**Crash Scenario:**
1. Attacker gains access to the repository.
2. Attacker retrieves `API_KEY`, `CHROMA_AUTH_TOKEN`, and `REDIS_URL` (including password).
3. Attacker can authenticate against any deployed instance using these default/leaked keys.

**Minimal Reproduction:**
Examine `docker-compose.yml` for `API_KEY`, `CHROMA_AUTH_TOKEN`, and `REDIS_URL`.

**Root Cause:**
Security best practices were bypassed during infrastructure setup.

**Fix (before -> after):**
```yaml
# Before
- API_KEY=sentinel-secret-api-key
- CHROMA_AUTH_TOKEN=sentinel-chroma-bearer-token

# After
- API_KEY=${API_KEY}
- CHROMA_AUTH_TOKEN=${CHROMA_AUTH_TOKEN}
```

---

## BUG-002

**Severity:** HIGH
**Module:** Frontend
**File:** Multiple files in `src/`
**Language:** TypeScript

**Description:**
Many Tauri `invoke` calls are made without `.catch()` or being wrapped in `try/catch` blocks.

**Crash Scenario:**
1. A Tauri command fails (e.g., database error or sidecar unavailable).
2. The promise rejects.
3. No error handler catches the rejection.
4. UI may hang or become unresponsive as state is never updated to reflect the failure.

**Minimal Reproduction:**
In `src/components/GapReport/GapReport.tsx`:
```typescript
const result = await invoke('analyze_gaps', { rfpId });
// if analyze_gaps fails, the following code is never reached and the error is unhandled
```

**Root Cause:**
Inconsistent error handling for asynchronous IPC calls.

**Fix (before -> after):**
```typescript
# Before
const result = await invoke('analyze_gaps', { rfpId });

# After
try {
  const result = await invoke('analyze_gaps', { rfpId });
} catch (error) {
  console.error('Failed to analyze gaps:', error);
  // handle error in UI
}
```

---

## BUG-003

**Severity:** MEDIUM
**Module:** Tauri Shell
**File:** Multiple files in `src-tauri/src/`
**Language:** Rust

**Description:**
Extensive use of `lock().unwrap()` on Mutexes.

**Crash Scenario:**
1. A thread holding a lock on `HunterRegistry` or similar panics.
2. The Mutex becomes "poisoned".
3. Any subsequent attempt to acquire the lock via `.lock().unwrap()` will panic the calling thread.
4. If this happens in a Tauri command thread, the command will fail and potentially affect application stability.

**Minimal Reproduction:**
Grep for `lock().unwrap()` in `src-tauri/src/`.

**Root Cause:**
Insecure handling of potentially poisoned Mutexes.

**Fix (before -> after):**
```rust
# Before
let mut guard = registry.active_hunts.lock().unwrap();

# After
let mut guard = registry.active_hunts.lock().map_err(|e| SentinelError::Sidecar(format!("Lock poisoned: {}", e)))?;
```

---

## BUG-004

**Severity:** MEDIUM
**Module:** Hunter Sidecar
**File:** `sidecars/hunter/src_py/scraper_engine.py`
**Language:** Python

**Description:**
`_extract_with_ollama` raises `RuntimeError` if no models are installed in Ollama.

**Crash Scenario:**
1. User triggers a hunt.
2. Hunter sidecar reaches extraction phase.
3. Ollama is online but has no models pulled.
4. `available_models` is empty.
5. `RuntimeError` is raised.
6. The gRPC stream is terminated with an `INTERNAL` error, but the error message seen by the user might be cryptic.

**Minimal Reproduction:**
Start Ollama without pulling any models, then trigger a hunt.

**Root Cause:**
Incomplete handling of missing LLM models at runtime.

**Fix (before -> after):**
```python
# Before
if not available_models:
    raise RuntimeError("...")

# After
if not available_models:
    await reporter.report_progress("Error: No Ollama models found. Please pull a model.")
    return [] # Gracefully return empty list or specific error event
```

---

## BUG-005

**Severity:** LOW
**Module:** Proto Contracts
**File:** `sidecars/worker/src_py/worker.proto`
**Language:** Protobuf

**Description:**
The `worker.proto` file is located within the worker sidecar directory instead of the central `proto/` directory.

**Crash Scenario:**
1. Developer modifies a message in `proto/` but misses `worker.proto`.
2. Inconsistent definitions lead to serialization errors at runtime when the Tauri shell tries to communicate with the worker.

**Minimal Reproduction:**
Compare the location of `worker.proto` with other `.proto` files.

**Root Cause:**
Architectural inconsistency.

**Fix (before -> after):**
Move `sidecars/worker/src_py/worker.proto` to `proto/worker.proto` and update build scripts/imports.

---

## BUG-006

**Severity:** HIGH
**Module:** Infrastructure
**File:** `docker-compose.yml`
**Language:** YAML

**Description:**
Missing healthchecks for `hunter`, `gap-engine`, and `jaeger`.

**Crash Scenario:**
1. `docker compose up` is executed.
2. Tauri app starts and tries to connect to `hunter` or `gap-engine`.
3. Sidecars are still initializing or have failed to start.
4. Tauri app receives connection refused errors.
5. Since there are no healthchecks, Docker doesn't know the services are unhealthy and won't restart them automatically if they hang.

**Minimal Reproduction:**
Examine `docker-compose.yml` for `healthcheck` sections in these services.

**Root Cause:**
Incomplete infrastructure monitoring configuration.

**Fix (before -> after):**
Add `healthcheck` blocks using `grpc_health_probe` or simple `nc`/`curl` checks if applicable.

---

## BUG-007

**Severity:** MEDIUM
**Module:** RAG Sidecar
**File:** `sidecars/rag/src_py/server.py`
**Language:** Python

**Description:**
`Ingest` method returns `status="error"` upon exception but doesn't set gRPC status code correctly in all paths, or caller might only check status string.

**Crash Scenario:**
1. `ingest_document` fails.
2. Exception caught, `context.set_code(grpc.StatusCode.INTERNAL)` is called.
3. `RagServiceServicer.Ingest` returns `IngestResponse(status="error")`.
4. If the Rust caller only checks the gRPC result `Ok(response)` and doesn't inspect `response.status`, it might assume success.

**Minimal Reproduction:**
Force an error in `ingest_document` and observe the response in the Rust client.

**Root Cause:**
Ambiguous success/failure signaling (using both gRPC codes and response fields).

**Fix (before -> after):**
Standardize on gRPC error codes and ensure the response object clearly indicates failure if the RPC technically succeeds.

---

## BUG-008

**Severity:** MEDIUM
**Module:** Hunter / RAG / Gap Engine Sidecars
**File:** `sidecars/hunter/src_py/server.py` (and others)
**Language:** Python

**Description:**
The `TracingServerInterceptor` incorrectly calls the `continuation` a second time if an exception occurs during the first call within the `try` block.

**Crash Scenario:**
1. A gRPC request is received.
2. `TracingServerInterceptor.intercept_service` is called.
3. It starts a span and awaits `continuation(handler_call_details)`.
4. If the handler raises an exception, the `except Exception:` block is triggered.
5. It then returns `await continuation(handler_call_details)` AGAIN.
6. This causes the RPC handler to be executed twice if it fails, which may have side effects or hide the original error's context.

**Minimal Reproduction:**
Trigger an RPC call that is guaranteed to fail (e.g., invalid input that causes an exception in the servicer). Observe logs showing the handler being entered twice.

**Root Cause:**
Incorrect implementation of a fallback in the interceptor's exception handler.

**Fix (before -> after):**
```python
# Before
        try:
            # ...
            with tracer.start_as_current_span(f"gRPC {method}") as span:
                # ...
                return await continuation(handler_call_details)
        except Exception:
            return await continuation(handler_call_details)

# After
        try:
            # ...
            with tracer.start_as_current_span(f"gRPC {method}") as span:
                # ...
                return await continuation(handler_call_details)
        except Exception:
            # Log the tracing failure but don't re-execute continuation if it was already called
            # Actually, the try should only wrap the tracing setup, not the continuation call itself.
            pass
        return await continuation(handler_call_details)
```

---

## BUG-009

**Severity:** MEDIUM
**Module:** Gap Engine Sidecar
**File:** `sidecars/gap-engine/src_py/server.py`
**Language:** Python

**Description:**
The `GapEngineServiceServicer` class definition uses a conditional inheritance that can lead to a `NameError` if proto stubs are missing, instead of a clean error message.

**Crash Scenario:**
1. Proto stubs (`gap_engine_pb2_grpc.py`) are missing or fail to import.
2. The `try/except` block around the import passes silently.
3. The class `GapEngineServiceServicer` is defined.
4. The `if 'gap_engine_pb2_grpc' in sys.modules` check might be inconsistent with the actual availability of the name in the local scope if the import was attempted but failed or was skipped.
5. More importantly, `gap_engine_pb2_grpc.add_GapEngineServiceServicer_to_server` is called later, which WILL crash if the import failed.

**Minimal Reproduction:**
Delete `sidecars/gap-engine/src_py/gap_engine_pb2_grpc.py` and start the server.

**Root Cause:**
Incomplete error handling for mandatory dependencies.

**Fix (before -> after):**
Remove the `try/except` and the conditional inheritance, or handle the `ImportError` by exiting the process with a clear error message.

---

## BUG-010

**Severity:** HIGH
**Module:** Infrastructure / Hunter Sidecar
**File:** `sidecars/hunter/src_py/scraper_engine.py`
**Language:** Python

**Description:**
Dynamic gateway IP resolution in Docker environments relies on reading `/proc/net/route`, which might fail or return an incorrect IP in complex network topologies (e.g., custom Docker networks).

**Crash Scenario:**
1. Hunter sidecar runs in a Docker container.
2. It needs to connect to Ollama on the host or another container.
3. `/proc/net/route` doesn't contain a default gateway in the expected format.
4. `gateway_ip` remains "172.19.0.1" (hardcoded fallback).
5. If the actual gateway/network is different, Ollama connection fails with a timeout or connection refused.

**Minimal Reproduction:**
Run the sidecar in a Docker network where the gateway is not the first address or `/proc/net/route` is inaccessible.

**Root Cause:**
Brittle network discovery logic.

**Fix (before -> after):**
Use service names (e.g., `http://ollama:11434`) and rely on Docker's internal DNS, which is already partially implemented but overridden by this logic if `localhost` is detected.

---

## BUG-011

**Severity:** MEDIUM
**Module:** Worker Sidecar
**File:** `sidecars/worker/src_py/worker.py`
**Language:** Python

**Description:**
The background worker loop (`run_worker`) uses a generic `except Exception:` block that catches and logs errors but continues the loop. If a persistent error occurs (e.g., malformed payload that `process_job` doesn't handle), it will keep popping and failing on the same or subsequent jobs without any circuit breaker.

**Crash Scenario:**
1. A job with a payload that causes a specific unhandled exception in `process_job` is enqueued.
2. `run_worker` pops it, calls `process_job`, catches the exception.
3. It sleeps for 2 seconds and continues.
4. If there are many such jobs, or if the error causes resource leaks, the worker becomes effectively stuck in a failure loop.

**Minimal Reproduction:**
Enqueue a job with a payload that crashes `process_job` (e.g., missing required fields that are not guarded).

**Root Cause:**
Lack of a dead-letter queue or max retry logic for background tasks.

**Fix (before -> after):**
Implement a retry limit or move failing jobs to a separate "failed_jobs" list in Redis.

---

## BUG-012

**Severity:** MEDIUM
**Module:** Tauri Shell / DB
**File:** `src-tauri/src/db/queries.rs`
**Language:** Rust

**Description:**
Database queries use `.unwrap()` or `.unwrap_or_default()` inside `query_map` closures, which can lead to panics or silent data corruption if the database schema ever drifts or contains unexpected nulls in supposedly non-null columns.

**Crash Scenario:**
1. A database migration fails or the `sentinel.db` is manually edited.
2. A required column (e.g., `id` or `name`) is missing or null.
3. `fetch_portals` is called.
4. `row.get(0).unwrap_or_default()` might provide a default value (like an empty string) that violates application logic elsewhere.
5. If `.unwrap()` is used (though less common in this file based on initial check), it panics the thread.

**Minimal Reproduction:**
Modify `sentinel.db` to have a null in a column accessed via `.unwrap()` or check `queries.rs` for `unwrap()` calls on database fields.

**Root Cause:**
Insecure database field extraction.

**Fix (before -> after):**
Use `?` within the closure to propagate errors gracefully to `query_map`, which then returns a `Result`.
