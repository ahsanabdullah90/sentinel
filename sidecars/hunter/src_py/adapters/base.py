"""Base Portal Adapter Module

Defines the abstract interface for portal-specific scraping adaptations.
"""

from abc import ABC, abstractmethod

class PortalAdapter(ABC):
    """Abstract base class representing a portal-specific routing and parsing adapter."""

    @abstractmethod
    def matches(self, base_url: str) -> bool:
        """Return True if this adapter is suitable for the given portal URL.

        Args:
            base_url: The portal's base URL.
        """
        pass

    @abstractmethod
    def supports_direct_query(self) -> bool:
        """Return True if the portal supports direct URL routing via query parameters."""
        pass

    @abstractmethod
    def build_search_url(self, base_url: str, keyword: str) -> str:
        """Build the direct search results URL for the given keyword.

        Args:
            base_url: The portal's base URL.
            keyword: The search keyword (e.g. "RFP").
        """
        pass
