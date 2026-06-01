# Module: Tauri Shell

## Purpose
The Tauri shell acts as the secure desktop container and orchestrator for the Sentinel RFP Agent. It manages the application's desktop windowing, provides a secure IPC bridge for the frontend UI, manages the SQLite database files, and acts as the central Process Manager that spawns and monitors the local Python sidecars.

## Language & Runtime
- **Language**: Rust
- **Framework**: Tauri v2
- **Key Libraries**:
  - `rusqlite`: Interface for local SQLite database management.
  - `tokio`: Async runtime for parallel background sidecar stream processing.
  - `serde_json`: High-performance JSON serialization for JSON-RPC 2.0.
  - `tauri-plugin-shell`: Core Tauri plugin used to securely spawn local sidecars.
- **Entry point**: `src-tauri/src/main.rs` (delegates window and lifecycle setups to `lib.rs`).

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

## Process Manager & Sidecar IPC
Tauri acts as the exclusive process orchestrator. It does not bind sidecars to local TCP network ports.
- **IPC Protocol**: Standard JSON-RPC 2.0 over standard input (`stdin`) and standard output (`stdout`) pipes.
- **Lifecycle Control**: Sidecars are spawned as child processes when a command executes. Dropping the sidecar handle automatically terminates the child process cleanly.
- **Mutex Lock Safety**: Processes are protected by Mutex locks to synchronize command triggers safely. Mutex poisoning is mitigated by recovering locks under panic via `.lock().unwrap_or_else(|poisoned| poisoned.into_inner())`.

## Dependencies
### Internal
| Module | How consumed |
|--------|-------------|
| Python Sidecars | Managed as child processes via standard input/output streams |

### External
| Package | Version | Purpose |
|---------|---------|---------|
| tauri | 2.x | Desktop shell framework |
| tokio | 1.x | Async process monitoring |
| rusqlite | 0.31 | SQLite interface |

## Data Flow
1. **Request**: UI triggers a Tauri command via `invoke('command_name')`.
2. **IPC Forwarding**: Tauri commands check process availability, format parameters as a JSON-RPC 2.0 request, and write to the sidecar's `stdin`.
3. **Execution**: Sidecar processes request, writes standard logs to `stderr`, and streams progress/results as JSON-RPC 2.0 messages to `stdout`.
4. **Response**: Rust reads sidecar's `stdout`, parses the JSON-RPC response, updates `sentinel.db` if necessary, and forwards updates to the UI.
