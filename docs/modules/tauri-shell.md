# Module: Tauri Shell

## Purpose
The Tauri shell acts as the secure desktop container and orchestrator for the Sentinel RFP Agent. It manages the lifecycle of the application, provides a secure IPC bridge between the frontend and backend services, handles local data persistence via SQLite, and manages gRPC communication with the Python-based sidecars.

## Language & Runtime
- **Language**: Rust
- **Framework**: Tauri v2
- **Key Libraries**: Tonic (gRPC client), Tokio (async runtime), Rusqlite (SQLite), Serde (serialization), OpenTelemetry (tracing).
- **Entry point**: `src-tauri/src/main.rs` (delegates to `lib.rs`)

## Public Interface
### Tauri Commands (`#[tauri::command]`)
- **System**: `bootstrap_system`, `check_ollama_status`, `get_ollama_models`, `extract_pdf_text_from_bytes`
- **Database (Portals)**: `get_portals`, `save_portal`, `delete_portal`, `toggle_portal_status`, `finish_active_hunt`
- **Database (Opportunities)**: `get_opportunities_list`, `get_opportunity_detail`, `update_opportunity_status`, `delete_opportunity`
- **Database (Attachments)**: `get_attachments`, `save_attachment`, `delete_attachment`, `update_attachment_text`, `get_attachment_bytes`
- **Database (Drafts & KB)**: `get_proposal_drafts`, `save_proposal_draft`, `update_proposal_draft`, `delete_proposal_draft`, `get_knowledge_base`, `save_knowledge_item`, `delete_knowledge_item`
- **Hunting**: `start_hunt_session`, `stop_hunt_session`, `detect_portal`
- **AI/RAG**: `analyze_gaps`, `generate_chat_response`, `generate_vision_description`, `ingest_document`, `generate_draft`
- **Scheduler**: `get_scheduler_timestamp`, `set_scheduler_timestamp`

## Internal Structure
- `src-tauri/src/commands/`: Command implementations organized by feature (hunting, db, drafting, etc).
- `src-tauri/src/db/`: SQLite schema (`schema.sql`), initialization logic, and query functions.
- `src-tauri/src/sidecar.rs`: Sidecar process management and streaming gRPC client implementations.
- `src-tauri/src/ipc.rs`: gRPC service definitions (via `tonic`) and client connection logic.
- `src-tauri/src/telemetry.rs`: OpenTelemetry OTLP tracing setup.
- `src-tauri/src/errors.rs`: Centralized `SentinelError` enum and serialization.

## Dependencies
### Internal
| Module | How consumed |
|--------|-------------|
| Python Sidecars | Consumed via gRPC over localhost (ports 50051-50054) |
| Proto Contracts | Rust code generated via `tonic-build` from `.proto` files |

### External
| Package | Version | Purpose |
|---------|---------|---------|
| tauri | 2 | Desktop framework |
| tonic | 0.11 | gRPC client/server |
| tokio | 1.38 | Async runtime |
| rusqlite | 0.31 | SQLite interface |

## Configuration
| Variable | Required | Default | Crash if missing? |
|----------|----------|---------|-------------------|
| ENV | No | development | No |
| API_KEY | Yes (prod) | sentinel-secret-api-key | Yes (panics in prod) |
| CHROMA_AUTH_TOKEN | Yes (prod) | - | Yes (panics in prod) |
| REDIS_URL | Yes (prod) | - | Yes (panics in prod) |

## Data Flow
- **IPC**: React calls `invoke('command')`, Rust executes handler.
- **Persistence**: Commands read/write to `sentinel.db` via `rusqlite`.
- **Sidecars**: Rust creates gRPC clients (`HunterServiceClient`, etc.) and forwards requests. Streaming responses from sidecars are emitted back to frontend as Tauri events.

## Startup Sequence
1. `validate_env()` checks required production variables.
2. `telemetry::init_telemetry()` starts OpenTelemetry tracing.
3. Tauri builder initializes plugins (`shell`, `sql`, `opener`).
4. SQLite database is initialized/migrated (`db::init()`).
5. Application starts and waits for frontend `bootstrap_system` call.
