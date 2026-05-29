"""Brightspyre Portal Adapter Module

Implements portal-specific adapter rules for Brightspyre.
"""

from urllib.parse import quote
from sidecars.hunter.src_py.adapters.base import PortalAdapter

class BrightspyreAdapter(PortalAdapter):
    """Portal adapter for the Brightspyre job portal."""

    def matches(self, base_url: str) -> bool:
        return "resume.brightspyre.com" in base_url

    def supports_direct_query(self) -> bool:
        return True

    def build_search_url(self, base_url: str, keyword: str) -> str:
        # Returns the direct search query URL
        return f"https://resume.brightspyre.com/jobs?query={quote(keyword)}"
