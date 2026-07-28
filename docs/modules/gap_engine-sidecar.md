# Module: Gap Engine Sidecar

## Purpose
The Gap Engine sidecar parses compliance records and compares RFP opportunities against internal capabilities and compliance guidelines. It extracts mandatory requirements (e.g. security clearances, certifications, bonding limits) and identifies any compliance gaps or high-risk sections.

## Language & Runtime
- **Language**: Python 3.11
- **Key Libraries**:
  - `chromadb`: Vector database for RFP document context retrieval.
- **Entry point**: `sidecars/gap_engine/src_py/server.py`

## JSON-RPC Methods
- `analyze_gaps`: Accepts an RFP ID, queries ChromaDB for context, runs zero-shot compliance analysis via Ollama, and returns identified gaps.

## IPC Events
- `gap_report_generated`: JSON array of identified gaps (including gap area, description).
- `progress`: Pipeline stage updates during gap analysis.

## Module Structure
- `server.py`: JSON-RPC dispatcher for `analyze_gaps` method.
- `events.py`: Unified IPC event emission.
- `gap_analyzer.py`: Core orchestration (ChromaDB context retrieval → Ollama inference → event emission).
- `chroma_utils.py`: ChromaDB query abstraction.
- `ollama_utils.py`: Zero-shot auditing prompt builder and response parser.
- `gap_engine.py`: Backward-compatible import hub re-exporting `analyze_gaps`.
