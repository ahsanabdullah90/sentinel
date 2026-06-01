# Module: Gap Engine Sidecar

## Purpose
The Gap Engine sidecar parses compliance records and compares RFP opportunities against internal capabilities and compliance guidelines. It extracts mandatory requirements (e.g. security clearances, certifications, bonding limits) and identifies any compliance gaps or high-risk sections.

## Language & Runtime
- **Language**: Python 3.11
- **Key Libraries**:
  - `pydantic`: Schema validation for compliance rules.
- **Entry point**: `sidecars/gap-engine/src_py/server.py`

## IPC Interface (Standard I/O JSON-RPC 2.0)
Communicates with the Tauri host process using standard stdin/stdout stream pipes.
- **Methods Received**:
  - `analyze_gaps`: Accepts an opportunity data block, extracts key checklist items, compares them to active configuration policies, and writes analyzed gaps to stdout.
- **Events Emitted**:
  - `gap_analysis_complete`: JSON array of identified gaps (including gap description, severity, status, and recommendations).
  - `error`: Error payloads on parsing failures.

## Internal Structure
- `server.py`: Standard I/O listener and command parser.
- `gap_engine.py`: Compliance analysis heuristics.
