"""Generic Fallback Portal Adapter Module

Implements default fallback routing behavior for any unadapted portal.
"""

from .base import PortalAdapter

class GenericAdapter(PortalAdapter):
    """Fallback portal adapter that relies on visual heuristics and search form submissions."""

    def matches(self, base_url: str) -> bool:
        # Matches anything as a catch-all fallback
        return True

    def supports_direct_query(self) -> bool:
        return False

    def build_search_url(self, base_url: str, keyword: str) -> str:
        return base_url
