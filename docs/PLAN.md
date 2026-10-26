# DocuMind — Implementation Plan

Living document: phase status, completion criteria and the decision log. Each finished phase gets a
report in `docs/phase-reports/`.

## Status

| Phase | Scope | Status |
|---|---|---|
| 1 | Discovery and architecture | Done |
| 2 | Backend foundation | Done |
| 3 | Ingestion and indexing | Done |
| 4 | Search and retrieval | Done |
| 5 | Frontend and design | Done |
| 6 | Optional AI answers | Done |
| 7 | Integration hardening | Done |
| 8 | Automated testing and CI | Running on GitHub, all jobs green; failing-check demonstration pending a pull request |
| 9 | Security, accessibility, review | Done — see REVIEW.md |
| 10 | Packaging and presentation | Not started |

## Phases and completion criteria

A phase is complete only when every item in its "done when" list has been checked by running
something, not by inspection alone.

**2 — Backend foundation.** App factory, settings, logging with request IDs, error envelope, SQLite
engine with PRAGMAs, schema init incl. FTS5 + triggers, `/api/health`, `/api/ready`, `/api/config`,
security headers, ruff + mypy config, pinned deps and lock file.
*Done when:* `pytest` passes (health/ready/config, error envelope, schema created, FK cascade and FTS
triggers work); ruff and mypy are clean; server starts with `uvicorn`.

**3 — Ingestion and indexing.** Streamed upload, validation, storage, extraction (pypdf/TXT),
normalisation, chunking, background processing with concurrency cap, start-up recovery, duplicate
409, list/detail/chunks/file/delete endpoints. Decide on subprocess timeout for extraction.
*Done when:* tests cover valid PDF/TXT, wrong extension, fake PDF, oversize, empty, corrupt,
encrypted, image-only (no text) PDF, duplicate, unsafe filenames, chunk coverage, page/line
references, delete-during-processing, delete removes DB rows + FTS rows + file.

**4 — Search and retrieval.** FTS5 search with sanitised queries, phrase support, stop words,
excerpts with highlight offsets, document filter; evaluation corpus and script.
*Done when:* tests cover ranking on a fixed corpus, FTS operator injection, empty/long queries,
scope to `ready` docs; hit@1/hit@5 recorded in the phase report with known misses.

**5 — Frontend and design.** Angular 21 workspace, design tokens, shell + routing, library with
upload queue and polling, reader with chunk anchoring, search, Ask (retrieval-only first),
API-unavailable handling.
*Done when:* component/service tests pass; app run against the real backend in a browser at
desktop, tablet and mobile widths with every visible control exercised; defects found are fixed.

**6 — Optional AI answers.** Provider interface, OpenAI-compatible provider (httpx), prompt with delimited
untrusted sources, structured output, citation validation, timeout/error mapping.
*Done when:* tests with fake providers cover grounded answer, invented citation IDs, no citations,
`sufficient: false`, injected instructions in a source, timeout, auth error, provider disabled;
one manual run with a real key if the owner supplies one (otherwise documented as not run).

**7 — Integration hardening.** End-to-end walkthroughs, outage behaviour (backend stopped mid-use),
failed processing, duplicate submits, persistence across restart, loading/error state review.
*Done when:* the walkthrough checklist in the phase report is executed and all defects are fixed or
listed.

**8 — Testing and CI.** GitHub Actions: backend (ruff, mypy, pytest), frontend (lint, test, build),
Docker build. Deliberately broken commit on a branch to prove CI fails.
*Done when:* a clean-checkout CI run is green and the failing-check demonstration is recorded.

**9 — Security, accessibility, review.** File handling, validation, error disclosure, logging and
secrets, prompt injection, keyboard and responsive review.
*Done when:* `docs/REVIEW.md` lists every finding with its verification evidence and status.

**10 — Packaging and presentation.** Multi-stage Dockerfile (Angular build → Python runtime,
non-root user, no data or `.env` in the image), `.env.example`, `docs/DEPLOYMENT.md`, screenshots of
the real app, final README, demo script.
*Done when:* the image builds (in CI — Docker is not installed locally) and the documented run
commands are executed as written.

## Decision log

| # | Decision | Reason |
|---|---|---|
| D1 | Separate repository at `Desktop/DocuMind`, sibling to OpsHub | Separate product; OpsHub history stays untouched. |
| D2 | Python 3.14, FastAPI 0.162, SQLAlchemy 2.1, pypdf 6.21 | Installed runtime; all wheels verified for cp314. |
| D3 | Angular 21.2 (LTS), not 22 | Angular 22 needs Node ≥ 22.22.3; Node 22.14.0 is installed. |
| D4 | SQLite FTS5 + BM25 as the retrieval baseline | Transparent, testable, no extra services. Not described as semantic. |
| D5 | Schema init via `create_all` + versioned DDL, no Alembic | Alembic can't manage FTS5 tables/triggers; schema is small. |
| D6 | One file per upload request; background processing; polling | Real per-file progress and status with no extra infrastructure. |
| D7 | Duplicates (same SHA-256) rejected with 409 | Avoids duplicate search hits; deliberate and visible. |
| D8 | PDF chunks never span pages | Every citation has exactly one page number. |
| D9 | Single-user, no auth, bind to localhost | Brief allows it; no false privacy claims. |
| D10 | OpenAI-compatible chat API as the optional provider, via httpx behind an interface | Owner's choice (2026-10-25). Covers OpenAI and local servers (Ollama, LM Studio). |
| D13 | httpx2 instead of httpx | Starlette 1.10 (via FastAPI 0.162) deprecates httpx for its test client; httpx2 is the maintained successor. |
| D14 | `requires-python >=3.12`, constraints file for transitive pins | Lets reviewers on 3.12/3.13 install; CI must prove it (Phase 8). |
| D15 | Extraction runs in a spawned process with a 120 s hard timeout | pypdf has had infinite-loop and decompression-bomb bugs; a thread cannot be stopped. Costs about 2.4 s per document on Windows; 500 dense pages take 10 s. |
| D16 | The extraction worker gets a file path, not bytes; the parent also waits on the process sentinel | Large start-up payloads blocked forever when the worker died early; start-up crashes were only detected at the timeout. Both reproduced, then fixed. |
| D17 | `cryptography` added | Needed for AES-encrypted PDFs, including the common empty-password kind. |
| D18 | Interrupted documents are marked failed on restart, not re-queued | Avoids a crash loop if a document caused the shutdown; the user deletes and re-uploads. |
| D19 | Highlights from FTS5 `highlight()`, returned as offsets | Matches exactly what the index matched (stemming); no HTML in the API. |
| D20 | No synonyms, embeddings or chunk overlap yet | Evaluation: keyword questions 100% hit@5; misses are vocabulary gaps, none caused by chunk boundaries. Semantic retrieval is the documented next step. |
| D21 | Retrieval-only `POST /api/ask` built in Phase 5 | The Ask workspace needed a real endpoint; generation is layered on in Phase 6. |
| D22 | Angular 21.2 with exact pins and a `vite` override to 7.3.7 | npm 10.9 resolver crash on newer Vite's optional peers; 7.3.7 is what `@angular/build` pins. |
| D23 | Native `<dialog>`, no Angular CDK or UI kit | Platform modality and inert background; fewer dependencies. |
| D24 | 5xx without the API envelope = server unreachable | The API always sends its envelope; the dev proxy and reverse proxies do not. |
| D25 | Browser learns the model name, never the provider address or key | Enough to tell the user what answers; nothing an attacker could use. |
| D26 | Insufficient evidence shows the closest passages, not the model's explanation | The explanation is generated text; showing it without the answer framing would blur the line between sources and generation. |
| D27 | Live path checked against a local test double; no paid provider used | The brief forbids requiring a paid service; a real-model run remains a documented check. |
| D28 | FastAPI serves the built SPA (moved forward from Phase 10) | One process to run and test end to end; the SPA's security policy is exercised for real. |
| D29 | Angular critical-CSS inlining off | Its inline `onload` handler is blocked by the CSP; found before it shipped. |
| D30 | Playwright end-to-end suite (Chromium only) | Proportionate: 8 workflow tests in ~13 s prove the frontend and backend work together, repeatably in CI. |
| D31 | Host allow-list + cross-site write refusal | Live probes showed DNS-rebinding reads and cross-site uploads worked. |
| D32 | Async capacity limiter for queued processing | 120-upload burst stalled the API for 26 s; now worst 322 ms. |
| D33 | `RLIMIT_AS` on the extraction process (POSIX) | Decompression bombs; no portable Windows equivalent, documented. |
| D34 | axe-core audit in the end-to-end suite | Automated WCAG A/AA rules on every page, in CI. |
| D12 | Commits use `Moeletsi Melamu <moeletsimelamu03@gmail.com>`, set in the repo's local config | Owner's choice (2026-10-25). |
| D11 | Single container: FastAPI serves the built SPA | One process to run; same-origin, no CORS. |

## Open items

- None.
