# Module: Proto Contracts

## Purpose
The `proto/` directory contains the Protocol Buffer definitions that serve as the single source of truth for all gRPC communication between the Tauri shell (Rust) and the various sidecars (Python).

## Definitions
### Services
1. **HunterService** (`hunter.proto`)
   - `Detect`: Streaming URL analysis.
   - `Hunt`: Streaming RFP discovery results.
2. **RagService** (`rag.proto`)
   - `Ingest`: Document processing.
   - `Query`: Semantic search and generation.
3. **GapEngineService** (`gap_engine.proto`)
   - `AnalyzeGaps`: Compliance analysis.
4. **WorkerService** (`sidecars/worker/src_py/worker.proto`)
   - `EnqueueJob`: Asynchronous task queuing.
5. **Health** (`health.proto`)
   - Standard gRPC Health Checking protocol.

## Internal Structure
- `proto/*.proto`: Raw protobuf definitions.
- `proto/*_pb2.py`, `proto/*_pb2_grpc.py`: Pre-generated Python stubs (note: should ideally be generated at build time).

## Dependencies
- **Rust**: Compiled into Rust code via `tonic-build` (see `src-tauri/build.rs`).
- **Python**: Used by sidecars via `grpcio-tools` generated stubs.

## Data Flow
Contracts define the binary serialization format and RPC method signatures used across the entire system.

## Known Risks
- `worker.proto` is located inside the worker sidecar directory instead of the central `proto/` directory, diverging from the project's architectural pattern.
- Python stubs are checked into the repository, leading to potential desynchronization if the `.proto` files are modified without re-generating the stubs.
