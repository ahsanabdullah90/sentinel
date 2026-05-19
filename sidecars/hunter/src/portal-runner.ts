/* eslint-disable no-console */
import { PortalConfig } from './types.js';
import { TokenBucketRateLimiter } from './rate-limiter.js';
import { getStrategy } from './scraper-engine.js';

export class PortalRunner {
  private activePortals = new Map<string, TokenBucketRateLimiter>();

  public async runPortal(config: PortalConfig) {
    if (!this.activePortals.has(config.id)) {
      this.activePortals.set(
        config.id,
        new TokenBucketRateLimiter(Math.min(5, config.requestsPerMinute), config.requestsPerMinute)
      );
    }

    const rateLimiter = this.activePortals.get(config.id);
    if (!rateLimiter) {
      throw new Error(`Rate limiter not initialized for ${config.id}`);
    }

    // In a real implementation, we would check the active window first
    console.log(
      JSON.stringify({
        event: 'progress',
        portalId: config.id,
        message: `Starting hunt for ${config.name}`,
      })
    );

    try {
      const strategy = getStrategy(config.scraperModule);
      const opportunities = await strategy.execute(config, rateLimiter);

      for (const opp of opportunities) {
        console.log(JSON.stringify({ event: 'opportunity_found', data: opp }));
      }

      console.log(
        JSON.stringify({
          event: 'progress',
          portalId: config.id,
          message: 'Hunt completed successfully',
        })
      );
    } catch (error: unknown) {
      const message = error instanceof Error ? error.message : String(error);
      console.log(
        JSON.stringify({
          event: 'error',
          code: 'scrape_failed',
          message,
          suggestion: 'Check the portal configuration and try again.',
        })
      );
    }
  }
}
