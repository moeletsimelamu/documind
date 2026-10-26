# Phase 10 report — Packaging and presentation

Date: 2026-10-26.

## Delivered

- `Dockerfile` (multi-stage: Node 22.14.0 builds the frontend, `python:3.14.9-slim-trixie`
  runs the backend installed from `constraints.txt`; uid 10001; `/data` volume; Swagger UI off;
  `HEALTHCHECK` on `/api/ready`) and `.dockerignore`.
- `scripts/smoke-test.sh`: nine checks against a running instance — readiness, app shell and client
  routes, Swagger off, foreign `Host` refused, upload, processing, search, Ask (retrieval-only),
  delete including the search index.
- CI job *Container image · build and smoke test*: builds the image, asserts the non-root uid, an
  empty `/data` and no `.env*` file anywhere in the image, runs the container and the smoke test.
- `frontend/scripts/capture-screenshots.mjs` and five screenshots in `docs/screenshots/`, taken from
  the real application (production build served by the backend, real API, fictional documents
  from the evaluation set and an image-only PDF). The script is now covered by `format:check`.
- `docs/DEPLOYMENT.md`, `docs/DEMO.md`, the final `README.md`; ARCHITECTURE.md §15 (packaging) and
  status; PLAN.md decisions D35–D38.

## Verification

| Check | Result |
|---|---|
| Smoke test, locally | **9/9 passed** against the backend configured as in the image (production build, Swagger off, separate data directory, no access log), on Windows with Git Bash. |
| Screenshots | Captured with the script and reviewed one by one: library (5 documents, one *No text found*), search, reader at a highlighted passage on page 2, Ask with sources S1/S2, phone-width search. |
| Demo document command in DEMO.md | Run as written; produced the five files. |
| Backend `pytest` / ruff / format / mypy | **293 passed, 3 skipped** (POSIX-only memory-limit tests); clean |
| Frontend Prettier / unit tests / end to end | clean; **62 passed**; **14 passed** (8 workflows + 6 accessibility audits) |
| Container image in CI | [run 40312172099](https://github.com/moeletsimelamu/documind/actions/runs/40312172099) on `5b2c35f`: **all five jobs passed**, including *Container image · build and smoke test* — the image built, the uid/`/data`/`.env` assertions held, and the smoke test passed against the running container. (The job's step logs need a GitHub sign-in and were not read; a failed step would have failed the job.) |

## Not verified

- **The image has not been built or run on the development machine** — Docker is not installed
  there. All image claims rest on the CI job.
- No public deployment was made (decision D38).
- The documented `docker run` with `--env-file` for AI answers has not been run against a real
  model.
