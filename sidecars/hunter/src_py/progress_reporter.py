"""Progress Reporter Module

Provides structured real-time progress and opportunity reporting via stdout
for JSON-RPC IPC with the Tauri Rust backend.
"""

import json
from typing import Dict, Any, Optional, Callable, Awaitable

from sidecars.hunter.src_py.models import RFPOpportunity


class ProgressReporter:
    """Handles unified reporting of progress and findings to stdout.

    Args:
        portal_id: Identifier for the portal being scraped.
        on_event: Optional async callback to forward events to the IPC layer.
    """

    def __init__(
        self,
        portal_id: str,
        on_event: Optional[Callable[[str, Dict[str, Any]], Awaitable[None]]] = None
    ):
        self.portal_id = portal_id
        self.on_event = on_event

    async def report_progress(self, message: str) -> None:
        """Report a standard progress string."""
        event_data = {"portalId": self.portal_id, "message": message}
        print(json.dumps({"event": "progress", **event_data}), flush=True)
        if self.on_event:
            await self.on_event("progress", event_data)

    async def report_opportunity(self, opp: RFPOpportunity) -> None:
        """Report a discovered opportunity."""
        event_data = opp.model_dump(by_alias=True)
        print(json.dumps({"event": "opportunity_found", "data": event_data}), flush=True)
        if self.on_event:
            await self.on_event("opportunity_found", event_data)

    async def report_opportunity_updated(self, opp: RFPOpportunity) -> None:
        """Report an updated opportunity after deep crawling."""
        event_data = opp.model_dump(by_alias=True)
        print(json.dumps({"event": "opportunity_updated", "data": event_data}), flush=True)
        if self.on_event:
            await self.on_event("opportunity_updated", event_data)

    async def report_attachment_downloaded(
        self, opp_id: str, file_name: str, file_path: str
    ) -> None:
        """Report a downloaded attachment."""
        event_data = {
            "opportunityId": opp_id,
            "fileName": file_name,
            "filePath": file_path,
        }
        print(json.dumps({"event": "attachment_downloaded", "data": event_data}), flush=True)
        if self.on_event:
            await self.on_event("attachment_downloaded", event_data)

    async def report_portal_detected(self, search_selector: str, base_url: str) -> None:
        """Report successful search input selector detection."""
        event_data = {"url": base_url, "searchSelector": search_selector}
        print(json.dumps({"event": "portal_detected", "data": event_data}), flush=True)
        if self.on_event:
            await self.on_event("portal_detected", event_data)

    async def report_error(self, message: str) -> None:
        """Report an execution error."""
        event_data = {"portalId": self.portal_id, "message": message}
        print(json.dumps({"event": "error", **event_data}), flush=True)
        if self.on_event:
            await self.on_event("error", event_data)
