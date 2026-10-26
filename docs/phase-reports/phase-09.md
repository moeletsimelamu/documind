# Phase 9 report — Security, accessibility and review

Date: 2026-10-26. The full review, with every finding and its evidence, is in
[docs/REVIEW.md](../REVIEW.md).

## Findings fixed in this phase

| ID | Finding | Before → after (measured on a live server) |
|---|---|---|
| R1 | DNS rebinding: any `Host` served | foreign `Host` → 200 with the library → **400** |
| R2 | Cross-site uploads accepted | `Origin: https://evil.example` upload → 202 (document planted) → **403** |
| R3 | Upload burst froze the API | 120 uploads: accepted in 23.7 s, health up to 26 s → accepted in 0.9 s, worst health 322 ms |
| R4 | No memory cap on PDF parsing | `RLIMIT_AS` on the extraction process (Linux/macOS); out of memory → `too_large` |
| R5 | `undici` advisories in Angular's build tooling | scoped override to 7.30.1; `npm audit` 0, `pip-audit` 0 |

## Changes

- `middleware.py`: `HostAndOriginGuardMiddleware` (host allow-list; refuses POST/PUT/PATCH/DELETE
  that `Origin` or `Sec-Fetch-Site` mark as coming from another site). Setting
  `DOCUMIND_ALLOWED_HOSTS`.
- `pipeline.py`: `process_in_background` waits on an `anyio.CapacityLimiter` instead of a
  threading semaphore inside a pool thread. `anyio` became a declared, pinned dependency.
- `isolation.py`: optional memory limit for the worker; `DOCUMIND_EXTRACTION_MEMORY_LIMIT_MB`.
- `frontend/package.json`: `undici` override for `@angular/build`; `@axe-core/playwright` 4.13.0.
- `e2e/accessibility.spec.ts`: axe audit of six page states.

## Verification (2026-10-26, Windows)

| Check | Result |
|---|---|
| Backend `pytest` / ruff / mypy | **293 passed, 3 skipped** (the POSIX-only memory-limit tests); clean |
| Frontend unit tests / Prettier | **62 passed**; clean |
| End to end (`npm run e2e`) | **14 passed**: 8 workflows (now behind the host/origin guard) + 6 accessibility audits with **0 violations** |
| Mutation checks | Removing the limiter: concurrency test fails (6 jobs started at once). Removing a form label: axe reports "critical label". |
| Reflow | All pages at 320 px: no horizontal scrolling |
| Linux CI | [Run 40305335014](https://github.com/moeletsimelamu/documind/actions/runs/40305335014) on `fc8be74`: all four jobs passed (backend on Python 3.12 and 3.14, frontend, end to end incl. the accessibility audit). The memory-limit tests are skipped only when `memory_limit_supported()` is false; `test_memory_limit_support_matches_the_platform`, which asserts it is true off Windows, passed on Linux — so the three tests ran there and passed. (Step logs need a GitHub sign-in to view and were not read.) |

## Not verified

Screen readers, non-Chromium browsers, a real language model, penetration testing by a third
party — listed in REVIEW.md §5.
