# Sentinel RFP Agent — Master Implementation Guidelines

> **Status:** Living document. Updated with every sprint.
> **Last Updated:** 2026-05-14
> **Version:** 1.0.0

---

## 1. The Non-Negotiables

These rules are **absolute**. They cannot be relaxed for convenience, deadlines, or
test environments. Any PR that violates them is rejected immediately.

### 1.1 Rate-Limiting is Sacred

The hunting module MUST honour these constraints at all times.

| Parameter            | Value                                                                                          |
| -------------------- | ---------------------------------------------------------------------------------------------- |
| Token refill rate    | 15 tokens / minute per portal                                                                  |
| Max burst size       | 5 tokens                                                                                       |
| Inter-request jitter | 2 000 – 8 000 ms (via `crypto.getRandomValues`)                                                |
| Portal parallelism   | Serial only — never scrape two portals concurrently                                            |
| Back-off trigger     | Any HTTP 429 or CAPTCHA signal                                                                 |
| Back-off schedule    | 30 s → 60 s → 120 s → … → cap 15 min                                                           |
| Off-peak override    | Respect `activeWindowStart/End`; queue jobs outside window                                     |
| Dev bypass           | Only via `SENTINEL_DEV_BYPASS_RATE_LIMIT=true`; **must** `console.warn` on every bypassed call |

**Why:** Violating portal ToS puts the product and users at legal risk. Rate-limit
code changes **must be flagged explicitly in PR descriptions** and reviewed by a
second engineer (or the user) before merge.

### 1.2 Local-Only Data Handling

- Document content, KB text, draft text, and embeddings **never leave the device**.
- Ollama → `http://localhost:11434` only. ChromaDB → `http://localhost:8000` only.
- Credentials stored in SQLCipher-encrypted SQLite only (Sprint 2+).
- Tauri network permissions whitelist only `localhost:11434` and `localhost:8000` via
  the capability system (`capabilities/default.json`). No broad CSP.

### 1.3 HITL (Human-in-the-Loop) Gates

Two hard gates that **must never be auto-bypassed**:

| Gate                       | Trigger                | Required Action                                              |
| -------------------------- | ---------------------- | ------------------------------------------------------------ |
| **MFA / CAPTCHA**          | Portal login challenge | Pause hunt, emit desktop notification, await `resume()` call |
| **Final draft submission** | User clicks "Submit"   | Require explicit second confirmation; never auto-submit      |

### 1.4 TypeScript Strictness

- `"strict": true` in every `tsconfig.json`. No exceptions, no overrides.
- No `any` types. Use `unknown` + type guards where the type is truly unknown.
- All async functions wrapped in explicit error boundaries — no silent `catch` blocks.
- **Zod** for all external data validation: API responses, portal parse results,
  Ollama output, sidecar stdout messages, CLI args.

### 1.5 Rust / Tauri Backend Safety

- All filesystem and credential operations go through **Rust commands**. The frontend
  never accesses the filesystem directly via the Tauri FS API.
- Use `thiserror` for all error types. Surface them to the frontend as structured
  `SentinelError` JSON.
- **Zero `unwrap()` or `expect()`** in production paths. Use `?` propagation throughout.
- DB migrations run in the Tauri `setup()` hook before any command can be invoked.

---

## 2. Architecture Principles

### 2.1 Sidecar Communication Protocols

The application uses two protocols for communicating between the Rust Tauri core and individual sidecars based on performance and streaming needs:

#### A. Hunter Sidecar (gRPC Stream Protocol)
The Hunter sidecar is built in Python and runs a high-performance gRPC server on `localhost:50051`. 
- **Start / Trigger**: Rust core invokes gRPC client streams (`Hunt` / `Detect`).
- **Cancellation**: Rust drops the connection handle, triggering a clean Python `asyncio.CancelledError` which stops the active Playwright browser process immediately.
- **Event Flow**:
  - `progress` events → Rust maps to `sentinel://hunter/progress`
  - `opportunity_found` events → Rust maps to `sentinel://hunter/opportunity-found`
  - `portal_detected` events → Rust maps to `sentinel://hunter/portal-detected`

#### B. RAG & Gap-Engine Sidecars (JSON-Lines Protocol)
Other Node.js-based sidecars communicate via standard stdout JSON-lines parsed in real-time by the Rust sidecar spawner:

**Stdout** (sidecar → Rust → frontend events):

```jsonc
// Success event
{ "event": "opportunity_found", "data": { /* RFPOpportunity */ } }

// HITL gate
{ "event": "hitl_required", "type": "captcha" | "mfa", "portalId": "string" }

// Recoverable error
{ "event": "error", "code": "rate_limited", "retryAfter": 60 }

// Progress
{ "event": "progress", "portalId": "string", "message": "string" }
```

**Stderr** (structured logs, never consumed by Rust):

```jsonc
{ "level": "info" | "warn" | "error", "ts": "ISO8601", "msg": "string", "ctx": {} }
```

Rust parses stdout → emits Tauri events with the prefix `sentinel://`:

```
sentinel://system/ollama-status
sentinel://system/chroma-status
sentinel://ingest/progress
sentinel://draft/progress
```

### 2.2 Event-Driven UI Updates

React components **never poll** Rust commands for state. All real-time updates arrive
via `listen()` subscriptions. `useTauriEvent<T>(event)` hook handles subscription
lifecycle (auto-cleanup on unmount).

### 2.3 Portal Auto-Detection Flow

When a user supplies a portal URL, the detection sequence is:

```
1. Fetch URL HEAD + body snippet
2. Check for known public REST API patterns (/api/, OpenAPI spec link)
3. Check for login form markers (<input type="password">, OAuth redirects)
4. Check if content is publicly accessible without credentials
   → Returns: { authMethod, apiEndpoint?, loginUrl? }
```

All outputs are Zod-validated before being stored as `PortalConfig`.

### 2.4 Error Propagation Chain

```
Sidecar (JSON error on stdout)
  → Rust SentinelError { code, message, context }
    → Tauri invoke() rejection
      → useTauriInvoke() hook → error state
        → UI error boundary / toast notification
```

No error is swallowed silently at any layer.

---

## 3. Code Quality Standards

### 3.1 Naming Conventions

| Context                       | Convention                                             | Example                             |
| ----------------------------- | ------------------------------------------------------ | ----------------------------------- |
| Rust modules / functions      | `snake_case`                                           | `start_hunt_session`                |
| TypeScript functions          | `camelCase`                                            | `startHuntSession`                  |
| TypeScript types / interfaces | `PascalCase`                                           | `RFPOpportunity`                    |
| Tauri events                  | `sentinel://domain/kebab-event`                        | `sentinel://hunt/opportunity-found` |
| Tauri commands                | `snake_case` (Rust)                                    | `start_hunt_session`                |
| React components              | `PascalCase` files                                     | `OpportunityRow.tsx`                |
| React Context                 | `use` + Context Name + `Context`                        | `useAppContext`                     |
| CSS classes                   | Tailwind utilities only; no custom class proliferation | —                                   |

### 3.2 File Organisation Rules

- One component per file. No barrel exports that re-export implementation details.
- Global application state is managed via React Context in `src/context/AppContext.tsx`.
- Components consume shared state and Tauri service wrappers via the `useAppContext()` hook.
- Sidecar source lives under `sidecars/<name>/src/`. Compiled output to `dist/`.
- Tests co-located in `__tests__/` inside each sidecar, or in `src/__tests__/` for
  React. Never mix test files with source files.

### 3.3 Commit Message Format

```
<scope>(<module>): <imperative verb> <what>
```

| Scope   | Module examples                                 |
| ------- | ----------------------------------------------- |
| `feat`  | `hunter`, `rag`, `gap-engine`, `tauri`, `ui`    |
| `fix`   | `rate-limiter`, `ingest`, `db`                  |
| `test`  | `rate-limiter`, `portal-detector`, `gap-engine` |
| `docs`  | `master`, `adr`, `api`, `portal-tos-review`     |
| `chore` | `deps`, `tauri`, `ci`                           |

Examples:

```
feat(hunter): add token-bucket rate limiter with crypto jitter
fix(rag): handle scanned PDF fallback to Tesseract OCR
docs(adr): record decision to use python grpc sidecar for hunter
chore(tauri): whitelist portal domains in capability config
test(gap-engine): add fixture for missing insurance cert scenario
```

---

## 4. Testing Standards

| Module             | Framework                | Coverage Target |
| ------------------ | ------------------------ | --------------- |
| Rate limiter       | Vitest + fake timers     | ≥ 95%           |
| Portal detector    | Vitest + msw             | ≥ 80%           |
| Domain Zod schemas | Vitest                   | 100%            |
| Ingest pipeline    | Vitest + fixture files   | ≥ 80%           |
| Gap engine         | Vitest                   | ≥ 80%           |
| Rust commands      | `cargo test`             | ≥ 80%           |
| React components   | Vitest + Testing Library | ≥ 70%           |

**Strict rules:**

- No live portal HTTP requests in CI. Use recorded **HAR fixtures** for hunter tests.
- No live Ollama calls in tests. Use **msw** mock server returning fixture JSON.
- No live ChromaDB in tests. Use in-memory mock client.
- Integration tests (real Ollama + ChromaDB) are tagged `@integration` and run
  separately from the unit suite.

---

## 5. Security Checklist (per PR)

- [ ] No secrets or credentials in source code or config files
- [ ] New network endpoints? → Must be whitelisted in `capabilities/default.json`
- [ ] New filesystem writes? → Must go through Rust command, not frontend FS API
- [ ] New sidecar stdout event? → Must be documented in §2.1 and have a Zod schema
- [ ] Any rate-limiter change? → Explicitly flagged in PR description
- [ ] Any HITL gate change? → Requires user sign-off before merge

---

## 6. Documentation Trail Requirements

Every implementation phase must produce the following alongside code:

| Deliverable                             | Location                             | Trigger                            |
| --------------------------------------- | ------------------------------------ | ---------------------------------- |
| **Phase log**                           | `docs/phases/phase-N.md`             | Start + end of each phase          |
| **ADR** (Architectural Decision Record) | `docs/adr/NNNN-title.md`             | Any non-trivial design choice      |
| **API reference**                       | `docs/api/`                          | New Tauri command or sidecar event |
| **Portal ToS notes**                    | `docs/portal-tos-review/<portal>.md` | New portal added                   |
| **Sprint changelog**                    | `docs/changelog/sprint-N.md`         | End of sprint                      |
| **Known issues**                        | `docs/known-issues.md`               | Any deferred fix or gotcha found   |

### ADR Template (`docs/adr/NNNN-title.md`)

```markdown
# ADR-NNNN: <Title>

**Status:** Proposed | Accepted | Deprecated | Superseded by ADR-XXXX
**Date:** YYYY-MM-DD

## Context

<Why this decision was needed>

## Decision

<What was decided>

## Consequences

<Trade-offs, follow-up work, risks>
```

### Phase Log Template (`docs/phases/phase-N.md`)

```markdown
# Phase N — <Name>

**Status:** In Progress | Complete
**Started:** YYYY-MM-DD **Completed:** YYYY-MM-DD

## Files Created / Modified

| File              | Change                           |
| ----------------- | -------------------------------- |
| `path/to/file.ts` | Created — <one-line description> |

## Decisions Made

- <decision> → see ADR-XXXX

## Deviations from Plan

- <any diff from implementation_plan.md and why>

## Test Results

<paste relevant test output or link>

## Next Phase Dependencies

<what must be true before phase N+1 begins>
```

---

## 7. Dependency Approval Policy

New dependencies require a note in the phase log answering:

1. **Why?** — What gap does this fill that existing deps cannot?
2. **License?** — Must be MIT, Apache-2.0, BSD, or ISC.
3. **Maintenance?** — Last commit < 6 months ago, or is a known stable library.
4. **Size impact?** — Bundle size delta for frontend deps.

---

## 8. Sprint Boundaries

| Sprint                   | Focus                                                                                               |
| ------------------------ | --------------------------------------------------------------------------------------------------- |
| **Sprint 1** _(current)_ | Scaffold, rate limiter, SAM.gov scraper, Ollama integration, ChromaDB ingest, dashboard shell       |
| **Sprint 2**             | SQLCipher credential storage, additional portals, RAG draft quality, gap engine real implementation |
| **Sprint 3**             | Distribution builds, auto-update, onboarding wizard, performance tuning                             |

Sprint 1 is **complete** when:

- [x] `cargo tauri dev` launches without errors
- [x] Rate limiter passes ≥ 95% test coverage
- [x] End-to-end: hunt session → opportunity appears in dashboard
- [x] PDF ingest → ChromaDB query returns relevant chunks
- [x] All Phase 0–6 phase logs are written
