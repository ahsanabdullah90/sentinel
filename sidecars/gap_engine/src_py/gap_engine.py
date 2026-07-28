"""Gap Engine Module — Backward-Compatible Import Hub

This module has been refactored into focused sub-modules:

  - ``events.py``       — Unified IPC event system
  - ``chroma_utils.py``  — ChromaDB query abstraction
  - ``ollama_utils.py``  — Ollama inference helpers
  - ``gap_analyzer.py``  — Core gap analysis orchestration

All public symbols are re-exported here so that existing import paths
(e.g. ``from gap_engine import analyze_gaps``) continue to work.
"""

# flake8: noqa: F401 — re-exports for backward compatibility
from sidecars.gap_engine.src_py.gap_analyzer import analyze_gaps
