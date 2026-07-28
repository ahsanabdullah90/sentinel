"""Scraper Engine Module — Backward-Compatible Import Hub

This module has been refactored into focused sub-modules:

  - ``progress_reporter.py``  — ProgressReporter
  - ``ollama_utils.py``       — extract_json, fetch_ollama_tags_sync, fetch_ollama_generate_sync
  - ``strategies.py``         — ScrapingStrategy hierarchy + get_strategy factory

All public symbols are re-exported here so that existing import paths
(e.g. ``from sidecars.hunter.src_py.scraper_engine import extract_json, get_strategy, ProgressReporter``)
continue to work without modification.
"""

# flake8: noqa: F401 — re-exports for backward compatibility
from sidecars.hunter.src_py.ollama_utils import (
    extract_json,
    fetch_ollama_tags_sync,
    fetch_ollama_generate_sync,
)
from sidecars.hunter.src_py.progress_reporter import ProgressReporter
from sidecars.hunter.src_py.strategies import (
    ScrapingStrategy,
    PublicApiStrategy,
    StaticHtmlStrategy,
    PlaywrightStrategy,
    GenericSearchStrategy,
    get_strategy,
)
