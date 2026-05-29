"""Hunter Portal Adapters Package

Handles registration and dynamic resolution of site-specific portal adapters.
"""

from typing import List
from sidecars.hunter.src_py.adapters.base import PortalAdapter
from sidecars.hunter.src_py.adapters.brightspyre import BrightspyreAdapter
from sidecars.hunter.src_py.adapters.generic import GenericAdapter

# Order matters: site-specific adapters must come first, generic fallback last
_REGISTRY: List[PortalAdapter] = [
    BrightspyreAdapter(),
    GenericAdapter(),
]

def resolve_adapter(url: str) -> PortalAdapter:
    """Find and return the first matching PortalAdapter for the given URL.

    Args:
        url: The base URL of the portal.

    Returns:
        The matched PortalAdapter instance.
    """
    for adapter in _REGISTRY:
        if adapter.matches(url):
            return adapter
    return GenericAdapter()
