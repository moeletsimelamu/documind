# DocuMind

A document knowledge assistant: upload PDFs and text files, search their contents, and ask
questions whose answers point back to the exact passages they came from.

**Status: in development.** The backend foundation (Phase 2) is in place: configuration, logging,
error handling, the SQLite schema with a full-text index, and health/readiness endpoints. Document
upload, search, question answering and the web interface are not built yet. See
[docs/PLAN.md](docs/PLAN.md) for progress, [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) for the
technical design and [docs/DESIGN.md](docs/DESIGN.md) for the interface design.

## Running the backend (development)

Requires Python 3.12 or later (tested on 3.14).

```bash
cd backend
python -m venv .venv
.venv/Scripts/python -m pip install -c constraints.txt -e ".[dev]"   # macOS/Linux: .venv/bin/python
.venv/Scripts/python -m uvicorn documind.main:create_app --factory --port 8000
```

The API listens on `http://127.0.0.1:8000`; interactive API docs are at `/api/docs`. Data is
written to `backend/data/` (git-ignored). Settings are listed in [.env.example](.env.example).

DocuMind has no user accounts: anyone who can reach the server can read and delete every
document. Keep it bound to localhost unless you put authentication in front of it.

## Checks

```bash
cd backend
.venv/Scripts/python -m pytest
.venv/Scripts/ruff check .
.venv/Scripts/mypy
```
