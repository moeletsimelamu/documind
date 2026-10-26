# Phase 7 report — Integration hardening

Date: 2026-10-26

## Built

- **One-process production mode:** `spa.py` serves the built frontend when `DOCUMIND_STATIC_DIR` is
  set — immutable caching for hashed bundles, `no-cache` for `index.html`, SPA fallback for
  client routes, real 404s for missing assets, no fallback for `/api/*`, containment to the build
  directory. 15 tests.
- **End-to-end suite:** `frontend/e2e/workflows.spec.ts` with Playwright 1.64.0 (Chromium):
  `npm run e2e` builds the frontend, starts the backend serving it on port 8765 with a fresh data
  directory, and runs 8 workflow tests in order. Each test fails on any console error or uncaught
  exception except expected 4xx responses.

## Verification (2026-10-26)

| Check | Result |
|---|---|
| Backend `pytest` / ruff / mypy | **265 passed**; clean |
| Frontend unit tests / prettier / build | **62 passed**; clean |
| End-to-end (`playwright test`) | **8 passed** in ~13 s: empty state; upload of a text PDF, a text file, an image-only PDF and a `.docx` with the right outcome for each; duplicate rejected with a link to the original; top-bar search → result → reader focused on the passage; reload of a document URL; Ask with an answer and with no answer; delete via dialog → gone from library and search; not-found page |
| Mutation checks | Removing the build-directory containment check let three encoded `..` paths read a file outside it (tests failed). Re-enabling critical-CSS inlining made the end-to-end suite fail on the CSP violation. Both reverted. |
| Production mode in the browser | `http://localhost:8000/library` from the FastAPI process: no console errors, stylesheet applied, component styles and fonts loaded; deep links return the app; hashed bundles `immutable`; missing `.js` → 404 |
| Restart persistence | Two documents uploaded, server stopped and restarted: both still `ready` with the same chunk counts, search still finds them, readiness `ok`. |
| Restart during processing | 500-page PDF uploaded, server stopped mid-processing, restarted: the document is `failed` / `interrupted` with the explanation; the others are untouched; no orphaned extraction process remained (checked the process list). |

## Defects found and fixed

1. **The production page would have rendered largely unstyled.** Angular's critical-CSS inlining
   loads the main stylesheet with `onload="this.media='all'"`; the content security policy blocks
   inline handlers, so the stylesheet would have stayed `media="print"`. Found by reading the built
   `index.html` before serving it; inlining is now off, and the end-to-end console guard catches a
   regression (demonstrated).
2. The end-to-end console guard initially failed on Chromium's own "Failed to load resource … 409"
   log for the intended duplicate rejection; expected 4xx responses are now ignored, 5xx and CSP
   errors are not.

## State review

Reviewed the loading, empty, error and retry paths of each page against the running app and code:
library (first load, load error with retry, empty, filtered-empty, processing poll, deleted
elsewhere), upload queue (client rejection, server rejection, duplicate link, network failure),
reader (loading, processing poll, failed, not found, missing passage, load-more errors), search
(initial, loading, results, none, error, same-query retry), Ask (empty, loading, error with retry,
one question at a time, all four response modes). No further inconsistencies found.

## Remaining

- The end-to-end suite runs in Chromium only; Firefox and WebKit are untested.
- It does not cover AI-generated answers (no model in CI); those are covered by backend and
  component tests and the Phase 6 browser checks against a test double.
