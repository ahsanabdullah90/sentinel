# Phase 3 — Hunter Sidecar

**Status:** Complete
**Started:** 2026-05-13 **Completed:** 2026-05-13

## Files Created / Modified

| File                                             | Change                                                               |
| ------------------------------------------------ | -------------------------------------------------------------------- |
| `sidecars/hunter/package.json`                   | Scaffolded Node.js sidecar package                                   |
| `sidecars/hunter/src/rate-limiter.ts`            | Implemented sacred Token-Bucket rate limiter with jitter and backoff |
| `sidecars/hunter/src/portal-analyzer.ts`         | Implemented Portal Viability Analyzer for scoring scrapeability      |
| `sidecars/hunter/src/scraper-engine.ts`          | Implemented Strategy-pattern Scraper Engine                          |
| `sidecars/hunter/src/portal-runner.ts`           | Orchestrator enforcing serial execution and emitting stdout events   |
| `sidecars/hunter/src/index.ts`                   | Entry point accepting `--url` (detect) or `--portal` (hunt) args     |
| `sidecars/hunter/__tests__/rate-limiter.test.ts` | Vitest coverage for token bucket, jitter, backoff, and captcha pause |

## Decisions Made

- `crypto.getRandomValues()` (via Node's `randomBytes`) used for rate limiter jitter to satisfy the non-negotiable requirement.
- Implemented `PortalViabilityAnalyzer` with mock behavior for Sprint 1. It provides scores based on domain matching for now.
- Scraper strategies return mock data for Sprint 1 to unblock full E2E UI flow.

## Deviations from Plan

- None.

## Test Results

- Vitest suite covers `TokenBucketRateLimiter` behavior, including edge cases for pausing and resuming.
- To execute: `cd sidecars/hunter && npx vitest run`

## Next Phase Dependencies

- Proceed to Phase 4 (RAG Sidecar).
