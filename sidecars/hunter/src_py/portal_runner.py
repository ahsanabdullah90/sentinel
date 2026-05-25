"""Portal Runner Module

Coordinates the execution of portal scraping configurations.  Manages
per-portal ``TokenBucketRateLimiter`` instances and delegates to the
appropriate ``ScrapingStrategy`` returned by ``get_strategy``.

Each discovered opportunity is emitted as a JSON-line event on stdout.
"""

import json
import logging
from typing import Dict, Any
from .rate_limiter import TokenBucketRateLimiter
from .scraper_engine import get_strategy

logger = logging.getLogger("hunter.portal_runner")


class PortalRunner:
    """Runs one or more portal configurations through the scraping pipeline.

    Attributes:
        active_portals: Map of portal ID → rate limiter instance.
    """

    def __init__(self):
        self.active_portals: Dict[str, TokenBucketRateLimiter] = {}

    async def run_portal(self, config: Dict[str, Any]) -> None:
        """Execute a full scrape for *config*.

        Args:
            config: Portal configuration dict containing at minimum
                ``id``, ``name``, ``baseUrl``, ``scraperModule``, and
                ``requestsPerMinute``.

        Raises:
            ValueError: If ``config`` is missing the ``id`` key.
        """
        portal_id = config.get("id")
        if not portal_id:
            raise ValueError("Portal config is missing 'id'")

        if portal_id not in self.active_portals:
            rpm = config.get("requestsPerMinute", 15)
            capacity = min(5, rpm)
            self.active_portals[portal_id] = TokenBucketRateLimiter(
                capacity=capacity,
                refill_rate=rpm,
                refill_interval_ms=60000
            )

        rate_limiter = self.active_portals[portal_id]

        print(json.dumps({
            "event": "progress",
            "portalId": portal_id,
            "message": f"Starting hunt for {config.get('name', 'Unknown Portal')} (Python)"
        }), flush=True)

        try:
            strategy_name = config.get("scraperModule", "static_html")
            strategy = get_strategy(strategy_name)
            opportunities = await strategy.execute(config, rate_limiter)

            for opp in opportunities:
                print(json.dumps({
                    "event": "opportunity_found",
                    "data": opp
                }), flush=True)

            print(json.dumps({
                "event": "progress",
                "portalId": portal_id,
                "message": "Hunt completed successfully"
            }), flush=True)

        except Exception as error:
            message = str(error)
            print(json.dumps({
                "event": "error",
                "code": "scrape_failed",
                "message": message,
                "suggestion": "Check the portal configuration and try again."
            }), flush=True)
            raise
