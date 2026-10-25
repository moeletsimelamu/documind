# Phase 2 report — Backend foundation

Date: 2026-10-25

## Built

| Module | Responsibility |
|---|---|
| `config.py` | `Settings` from `DOCUMIND_*` environment variables / `.env`, validated limits, API key as `SecretStr`, `llm_enabled` only when a model is set |
| `logging_setup.py` | Log format with the request ID on every line; Uvicorn's access log (which includes query strings) raised to WARNING |
| `middleware.py` | One pure-ASGI middleware: request ID (generated, or a safe incoming `X-Request-ID` kept), access log without query strings, security headers with a path-specific CSP, and conversion of unhandled exceptions into a generic 500 envelope |
| `errors.py` | `AppError` / `NotFoundError` and handlers giving every error the same `{"error": {code, message, request_id, details?}}` shape; validation errors list location and message but never echo the input |
| `models.py` | `Document` and `Chunk` ORM models, status CHECK constraint, UTC-aware timestamps, `schema_meta` |
| `db.py` | Engine with SQLite PRAGMAs on every connection, `init_schema` (tables + FTS5 external-content index + insert/update/delete triggers + schema version), `session_scope` |
| `api/health.py` | `GET /api/health`, `GET /api/ready` (DB + FTS index + writable storage → 200/503), `GET /api/config` |
| `main.py` | `create_app(settings)` factory; lifespan creates directories and the schema |

Also: `pyproject.toml` with exact pins, `constraints.txt` (all 35 resolved packages),
`.env.example`, ruff and strict mypy configuration.

## Verification (all run on 2026-10-25, Windows, CPython 3.14.3)

| Check | Result |
|---|---|
| `pytest` | **36 passed** (config 7, database 12, errors/middleware 11, health 6) |
| `ruff check .` / `ruff format --check .` | clean |
| `mypy` (strict, pydantic plugin, 18 files incl. tests) | no issues |
| Tests detect regressions | Temporarily switching `foreign_keys` off made 3 DB tests fail; logging the query string made the access-log test fail. Both changes reverted. |
| Constraints file | Resolves in a fresh virtual environment (`pip install --dry-run -c constraints.txt -e ".[dev]"`) |
| Real server | `uvicorn documind.main:create_app --factory --port 8000` started, bound to 127.0.0.1; `/api/health`, `/api/ready`, `/api/config` returned 200 with the expected bodies and headers, an unknown path returned the 404 envelope, and `/api/docs` rendered Swagger UI in the in-app browser with no CSP errors |

What the tests cover: PRAGMAs; schema objects and version; idempotent init; refusal of a newer
schema version; FTS indexing with Porter stemming; re-indexing on update; **deleting a document
removes its chunks and their index rows** (via the database foreign key, not the ORM); orphan
chunks rejected; duplicate SHA-256 rejected; invalid status rejected by the database; rollback
on error; UTC round-trip; readiness 503 when storage is unusable; config never exposes the API
key or provider URL; error envelope for 404/405/415/422/500; 500 hides the exception message and
logs the traceback; request-ID handling; security headers; no query string in access logs.

## Changes from the Phase 1 design

- **httpx → httpx2.** FastAPI 0.162 depends on Starlette 1.10, whose test client emits a
  deprecation warning for httpx and prefers httpx2 (its maintained successor). With warnings
  treated as errors, the suite would not start. httpx2 2.16.0 is now the HTTP client for tests and
  for the future LLM provider.
- **Lock file** is `backend/constraints.txt` used as pip constraints, rather than a
  `requirements.lock`, so Windows-only transitive packages (colorama) are skipped on Linux.
- **`requires-python >=3.12`** rather than 3.14 only, so reviewers on older Python can install;
  only 3.14 has been tested so far. CI adds 3.12 in Phase 8.

## Not done / carried forward

- SPA static file serving (Phase 5/10).
- Early rejection of oversized request bodies by `Content-Length` (Phase 3, with uploads).
- The 500 response's security headers are covered; the CSP for the SPA is untested until the
  frontend exists.
