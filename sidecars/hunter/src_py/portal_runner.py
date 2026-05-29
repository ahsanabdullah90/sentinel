"""Portal Runner Module

Coordinates the execution of portal scraping configurations. Manages
per-portal ``TokenBucketRateLimiter`` instances and delegates to the
appropriate ``ScrapingStrategy``.
"""

import json
import logging
from typing import Dict, Optional, Callable, Any, Awaitable
from .rate_limiter import TokenBucketRateLimiter
from .scraper_engine import get_strategy, ProgressReporter
from .models import PortalConfig

logger = logging.getLogger("hunter.portal_runner")


class PortalRunner:
    """Runs one or more portal configurations through the scraping pipeline.

    Attributes:
        active_portals: Map of portal ID → rate limiter instance.
    """

    def __init__(self):
        self.active_portals: Dict[str, TokenBucketRateLimiter] = {}

    async def run_portal(
        self,
        config: PortalConfig,
        on_event: Optional[Callable[[str, Dict[str, Any]], Awaitable[None]]] = None
    ) -> None:
        """Execute a full scrape for *config*.

        Args:
            config: Validated PortalConfig Pydantic model.
            on_event: Optional async callback to receive events as they occur.
        """
        portal_id = config.id

        if portal_id not in self.active_portals:
            rpm = config.requests_per_minute
            capacity = min(5, rpm)
            self.active_portals[portal_id] = TokenBucketRateLimiter(
                capacity=capacity,
                refill_rate=rpm,
                refill_interval_ms=60000
            )

        rate_limiter = self.active_portals[portal_id]
        reporter = ProgressReporter(portal_id, on_event)

        await reporter.report_progress(f"Starting hunt for {config.name} (Python)...")

        try:
            strategy_name = config.scraper_module
            strategy = get_strategy(strategy_name)
            
            # The strategy will report each individual opportunity and step progress in real time
            await strategy.execute(config, rate_limiter, reporter)

            await reporter.report_progress("Hunt completed successfully")

        except Exception as error:
            message = str(error)
            err_data = {
                "portalId": portal_id,
                "code": "scrape_failed",
                "message": message,
                "suggestion": "Check the portal configuration and try again."
            }
            print(json.dumps({"event": "error", **err_data}), flush=True)
            if on_event:
                await on_event("error", err_data)
            raise
