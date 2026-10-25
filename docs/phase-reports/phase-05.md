# Phase 5 report — Frontend and design

Dates: 2026-10-26 (work spanned midnight from 2026-10-25)

## Built

- **Backend:** `POST /api/ask` in retrieval-only mode (`answering/service.py`, `api/ask.py`):
  returns the top six passages as `retrieval_only`, or `insufficient_evidence` when nothing
  matches; validates length and empty questions. 10 tests.
- **Frontend:** Angular 21.2 workspace in `frontend/` — app shell (top bar, navigation, global
  search, skip link, outage banner, toasts), library (drop zone + file button, upload queue with
  byte progress and processing state, name/status filters, table that becomes cards on narrow
  screens, delete confirmation), document reader (page dividers or line ranges, windowed loading,
  opening a cited passage), search (URL-driven, document scope, highlighted excerpts, honest
  empty state), Ask workspace (composer, scope, numbered sources, insufficient-evidence notice,
  retry), not-found page. Design tokens and shared styles in `src/styles.css`.

## Verification

| Check | Result |
|---|---|
| Backend `pytest` / ruff / mypy | **209 passed**; clean |
| Frontend `ng test` (Vitest + jsdom) | **55 passed** in 11 files |
| `prettier --check`, `ng build` (production) | clean; initial bundle 280 kB raw / 77 kB transferred; pages lazy-loaded; no budget warnings |

**Browser checks performed** (in-app browser, real backend on :8000, dev server on :4400):

1. Library empty state, then four files added through the real file input: `.docx` rejected
   client-side; two files became *Ready*; the image-only PDF became *No text found* with the
   server's explanation — all via the store's polling.
2. Library table at 1280 px (empty-page note, failure message, statuses); name filter
   (case-insensitive, "Showing 1 of 3"); status filter.
3. Delete via keyboard: dialog opens with focus on Cancel, Esc closes and returns focus to the
   trigger, Tab + Enter deletes; the server list confirms removal.
4. Reader: serif text, page divider, "1 page had no extractable text", download link.
5. Search typed in the form: URL updated, highlights, "lines 1–7", link to the passage; following it
   opened the reader at that passage, highlighted and focused.
6. Ask: answerable question → passages as S1…; unanswerable → "Not enough in your documents…".
7. 375 px: library, search, reader, Ask and not-found pages — no horizontal overflow (measured with
   `scrollWidth`); screenshots of library and search.
8. Outage: backend stopped → banner + inline message; backend restarted → banner cleared within
   the 5 s poll and the library reloaded; re-submitting the same search re-ran it.
9. Keyboard: first Tab shows "Skip to content"; visible focus ring on the dark top bar.

## Defects found in the browser and fixed

| # | Defect | Fix | Test now covering it |
|---|---|---|---|
| 1 | Upload queue started the *last* chosen files first | Items kept in chosen order | `upload-queue.service.spec` ("in the order they were chosen") |
| 2 | Focus fell to `<body>` after deleting (trigger removed with its row) | Focus moves to `<main>` when the trigger no longer exists, decided after render | browser check |
| 3 | "Open in document" ran on from the excerpt text | Excerpt host is a block | browser check |
| 4 | Ask field not cleared when Enter followed typing before a render; the next question was appended to the old text | Field cleared directly on submit | `ask-page.spec` ("clears the field at once") |
| 5 | Outage showed "unexpected response (500)" — the dev proxy's bare 500 | 5xx without the API envelope treated as unreachable | `api-error.spec`, `connection.service.spec` |
| 6 | Re-submitting an unchanged search did nothing (same URL) | Same query re-runs directly | `search-page.spec` |
| 7 | Stray space before a full stop; bare "3" for page count on mobile; "1 best matches" | Template and wording fixes | `ask-page.spec`; browser check |

Also found while writing tests: jsdom has no `HTMLDialogElement.showModal`, so `src/test-setup.ts`
provides a minimal stand-in; real dialog behaviour was checked in the browser (item 3).

## Not done / limits

- Screenshots for the README are taken in Phase 10, after Phase 6 changes the Ask page.
- Automated browser (end-to-end) tests are not in place; the checks above were run by hand
  through browser automation. Whether to add Playwright is decided in Phase 7/8.
- Accessibility was checked for keyboard paths, focus visibility, labels and contrast tokens; a
  screen-reader walkthrough and automated audit belong to Phase 9.
- The upload queue lives in memory: reloading the page during an upload loses the queue view (the
  server still finishes processing; the library shows the result).
