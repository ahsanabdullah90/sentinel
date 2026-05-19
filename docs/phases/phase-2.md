# Phase 2 — Rust Backend & SQLite

**Status:** Complete
**Started:** 2026-05-13 **Completed:** 2026-05-13

## Files Created / Modified

| File                                       | Change                                                                                                      |
| ------------------------------------------ | ----------------------------------------------------------------------------------------------------------- |
| `src-tauri/Cargo.toml`                     | Added `thiserror`, `uuid`, `tokio`, `tracing`, `tauri-plugin-sql`, `tauri-plugin-shell`                     |
| `src-tauri/src/errors.rs`                  | Created `SentinelError` via `thiserror` mapping to frontend JSON structure                                  |
| `src-tauri/src/db/schema.sql`              | Created SQLite schema with 4 tables (`portals`, `opportunities`, `requirements`, `gap_items`)               |
| `src-tauri/src/db/mod.rs`                  | Setup `tauri-plugin-sql` migration using `schema.sql`                                                       |
| `src-tauri/src/sidecar.rs`                 | Implemented supervisor that spawns Node.js scripts, translates stdout to Tauri events, and handles restarts |
| `src-tauri/src/commands/hunting.rs`        | Created IPC commands for start/stop hunt and detect portal                                                  |
| `src-tauri/src/commands/drafting.rs`       | Created IPC commands for ingest and generate draft                                                          |
| `src-tauri/src/commands/knowledge_base.rs` | Created IPC commands for KB add and search                                                                  |
| `src-tauri/src/lib.rs`                     | Wired up plugins, commands, and `tracing`                                                                   |

## Decisions Made

- `tauri-plugin-sql` is used to manage SQLite migrations on launch automatically.
- The `sidecar.rs` supervisor uses a simple stdout JSON-lines parser to funnel sidecar events to React safely.
- Sidecars will be spawned using `node` in development via `tauri-plugin-shell`.
- Replaced `sqlx::Error` `From` trait implementation with standard Error definitions to match Tauri v2 SQL plugin behavior.

## Deviations from Plan

- None.

## Test Results

- `cargo check` verified code compiles properly (to be run via `cargo test` / `dev`).

## Next Phase Dependencies

- Phase 3 (Hunter Sidecar) starts next.
