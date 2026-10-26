# DocuMind — Security, accessibility and engineering review

Date: 2026-10-26 (Phase 9). Reviewer: the implementing engineer; this is a self-review, not an
independent audit. Every "verified" entry names the test, measurement or probe behind it; claims
without evidence are listed under "Not verified".

**Scope:** the backend API and processing pipeline, the Angular frontend, the build and CI setup,
and the single-user trust model in ARCHITECTURE.md §1. DocuMind has no user accounts: anyone who
can reach the server can read and delete everything. It is designed to run on the user's own
machine, bound to `127.0.0.1`.

**Method:** dependency audits (`pip-audit`, `npm audit`); a search of the source for risky
patterns; live probes against a running production-mode server (before and after each fix);
mutation checks (temporarily removing a control to confirm a test fails); an automated
accessibility audit with axe-core; manual keyboard and reflow checks in the browser.

## 1. Findings

| ID | Area | Severity* | Finding | Status | Evidence |
|---|---|---|---|---|---|
| R1 | Network | High | **DNS rebinding.** The server answered for any `Host`, so a hostile website that re-points its domain to 127.0.0.1 could read the whole library from the user's browser. | **Fixed** | Probe: `Host: attacker.example` → 200 with the document list before; **400 `invalid_host`** after. 24 tests in `test_host_origin_guard.py`. |
| R2 | Network | Medium | **Cross-site writes.** Browsers send cross-site `multipart/form-data` POSTs without a preflight; any website could upload into the library (probe planted `planted-by-evil-site.txt`). DELETE and JSON POSTs were already blocked by the browser's preflight (no CORS). | **Fixed** | Probe: `Origin: https://evil.example` upload → 202 before, **403 `cross_origin_request`** after; same-origin upload still accepted. Tests cover `Origin`, `null` origin, `Sec-Fetch-Site: cross-site/same-site`, cross-site DELETE, and curl-style requests without those headers. |
| R3 | Availability | Medium | **Upload bursts froze the API.** Each queued document held one of the server's 40 shared worker threads while waiting for a processing slot. During a 120-file upload, `/api/health` took 6 s, 8 s and **26 s**; the whole UI would hang. | **Fixed** | Queued documents now wait on an async capacity limiter. Same probe after the fix: 120 uploads accepted in 0.9 s (was 23.7 s), worst health **322 ms**, none over 1 s. `test_processing_concurrency.py` fails if the limiter is removed (mutation-checked). |
| R4 | Availability | Medium | **No memory cap on PDF parsing.** A decompression-bomb PDF could exhaust memory; only a time limit existed. | **Fixed on Linux/macOS; open on Windows** | Extraction worker sets `RLIMIT_AS` (`DOCUMIND_EXTRACTION_MEMORY_LIMIT_MB`, default 1024); `MemoryError` → document `failed` / `too_large`. POSIX tests (allocation over the limit fails; 100 MB and a 200-page PDF succeed) passed in CI on Linux (run 40305335014); skipped on Windows, which has no portable equivalent. |
| R5 | Supply chain | Low | `undici` 7.29.1 inside Angular's build tool had three advisories (GHSA-4qv8-2p9j-2685, GHSA-f72v-6w45-q472, GHSA-xjj6-f33q-929c). Build-time only; never shipped to browsers. | **Fixed** | npm override scoped to `@angular/build` → 7.30.1; `npm audit`: 0. `pip-audit` on all 39 pinned Python packages: no known vulnerabilities. |
| R6 | Web | High (if shipped) | Production `index.html` loaded its stylesheet through an inline `onload` handler that the CSP blocks — the deployed page would have been largely unstyled. *(Found in Phase 7.)* | **Fixed** | Critical-CSS inlining off; the end-to-end suite fails on any CSP violation (demonstrated by re-enabling it). |
| R7 | Availability | Medium | The PDF worker could block forever, or be noticed only at the timeout, if it died during start-up. *(Found in Phase 3.)* | **Fixed** | Reproduced (hang with a 2 MB payload; 30 s to detect a crash); now path-only arguments and sentinel wait (0.4 s). |

\*Severity reflects DocuMind's intended use: one person, on their own machine.

## 2. Controls re-verified

| Area | Control | Verified by |
|---|---|---|
| File upload | Extension allow-list and content check (`%PDF-` signature; UTF-8/UTF-16-BOM text, no NUL bytes) | `test_validation.py`, `test_documents_api.py` (fake PDF, binary `.txt`, `.docx`, Latin-1) |
| | Size limit enforced while receiving (Content-Length and byte counting) and while copying | API tests; streamed-limit test proven to fail without the counter |
| | Generated storage names; display names stripped of paths, control and bidi characters, line breaks | `test_validation.py` (incl. `../`, `C:\`, U+202E, CRLF), traversal upload test |
| | Files stored outside any web root; served only as `attachment` with `nosniff` | `test_spa.py` (uploads unreachable via the app route), download test |
| | Parsing isolated in a process with time (and, on POSIX, memory) limits | `test_isolation.py`, Phase 3 measurements |
| Static files | Build directory containment, `/api/*` never served the app shell | `test_spa.py` (encoded `..`; mutation-checked) |
| Input | Pydantic validation; query/question length limits; 422 responses list location and message without echoing input | `test_errors_and_middleware.py`, search and ask API tests |
| Injection | SQL via SQLAlchemy parameter binding; FTS5 queries built only from quoted alphanumeric terms | `test_retrieval.py` (10 hostile queries) |
| | No HTML from the API; Angular interpolation only; no `innerHTML`/sanitizer bypass in the source (searched) | `excerpt.spec.ts`, search API test with `<script>` in a document |
| Errors | Uniform envelope; unhandled errors → generic 500 with request ID, traceback only in the log | `test_errors_and_middleware.py` |
| Secrets | API key held as `SecretStr`; never in `/api/config` or logs; `.env` git-ignored; no keys in history (scanned before the first push) | `test_config.py`, `test_health.py`, `test_openai_compatible.py` log test |
| Logging | IDs, sizes, codes and timings only — no document text, questions, query strings, file names or prompts; HTTP client's own URL logging silenced | source search of every log call; access-log and provider-log tests |
| Headers | `nosniff`, `no-referrer`, `DENY` framing, COOP, Permissions-Policy; CSP `default-src 'none'` for the API and `'self'` for the app; `no-store` on API responses | middleware and SPA tests; Phase 7 browser check (no violations) |
| Deletion | Record, chunks, index entries (FTS5 integrity-check) and file removed; orphans swept at start-up | `test_db.py`, `test_documents_api.py`, Phase 3 live check |
| AI answers | Untrusted passages escaped and delimited; citations validated against retrieval; uncited or invalid-only answers withheld; source details from the database | `test_prompt.py`, `test_answering.py` (incl. a document whose injected instructions a fake model obeys); mutation-checked |

## 3. Accessibility

| Check | Result |
|---|---|
| axe-core (WCAG 2.0–2.2 A/AA rules) on library, delete dialog, reader at a cited passage, search results, Ask with a response, not-found page | **0 violations** on all six (`e2e/accessibility.spec.ts`, runs in CI). Removing one label made it fail with "critical label" — the audit is effective. |
| Keyboard | Skip link; visible focus everywhere including the dark top bar; dialog opens on Cancel, Esc closes, focus returns to the trigger or to the page after a delete; citation markers and sources reachable and focused (Phases 5–6 browser checks; component tests) |
| Reflow (WCAG 1.4.10) | All pages at **320 px** wide: no horizontal scrolling (measured `scrollWidth` = 320) |
| Contrast | Every text/background token pair measured ≥ 4.5:1, control borders ≥ 3:1 (DESIGN.md §3) |
| Motion | No decorative animation; spinner slowed and smooth scrolling disabled under `prefers-reduced-motion` |
| Announcements | Polite live regions for upload progress, Ask responses and toasts; alerts for errors |

## 4. Accepted risks and limitations

- **No authentication or per-user isolation** (by design, ARCHITECTURE.md §1). Exposing DocuMind on a
  network needs an authenticating reverse proxy at minimum; `DOCUMIND_ALLOWED_HOSTS` must then name
  the public host.
- **No request rate limiting.** Size, page, character, concurrency and time limits bound each
  request, but a local process can still submit unlimited uploads (now without freezing the API).
- **Prompt injection is reduced, not prevented.** A manipulated passage can still shape the wording
  of an answer that cites real passages; the UI shows sources beside every answer and labels it as
  generated and fallible.
- **Hosted AI providers receive the question and retrieved passages.** Stated in the UI when AI
  answers are on; a local model avoids it.
- **Swagger UI** (`/api/docs`) loads assets from jsDelivr under a relaxed CSP limited to that path.
  It is on by default for development; the container image turns it off (Phase 10).
- **Extraction results are unpickled from the worker process.** The worker only runs our code, but a
  hypothetical code-execution flaw in the PDF parser would let a malicious file send a crafted
  object back to the server process. Isolation limits time and memory, not privileges.
- **Unexpected exceptions are logged with tracebacks**, whose messages could in rare cases include
  fragments of parser input.
- **No memory limit on Windows** (R4).
- **The library list is not paginated** (checked with 301 documents: fine; thousands untested).

## 5. Not verified

- Screen-reader use with NVDA, JAWS or VoiceOver.
- Browsers other than Chromium (Firefox, Safari/WebKit).
- Behaviour under a real language model (Phase 6 used a test double).
- Penetration testing by anyone other than the author.
