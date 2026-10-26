# DocuMind

A document knowledge assistant: upload PDFs and text files, search their contents, and ask
questions whose answers point back to the exact passages they came from.

**Status: in development.** Working today, through a web interface and the HTTP API: upload PDF
and text files and watch them being processed; browse, filter, read and delete documents; keyword
search with highlighted excerpts that open the document at the passage; and asking questions.
Without an AI model configured, answers are the most relevant passages. With an
OpenAI-compatible model configured (hosted, or local such as Ollama), answers are generated
from those passages, every statement cites one, and citations the server cannot match to a
retrieved passage are removed. Continuous integration and packaging are still to come. See
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
document. Keep it bound to localhost unless you put authentication in front of it. Other
websites open in your browser cannot use it: the server only answers for local host names and
refuses cross-site write requests (see [docs/REVIEW.md](docs/REVIEW.md)).

## Running the frontend (development)

Requires Node.js 22.12 or later (tested on 22.14). With the backend running on port 8000:

```bash
cd frontend
npm ci
npm start
```

Open `http://localhost:4200`. API calls are proxied to the backend.

## Running as one process (production build)

```bash
cd frontend
npm run build
cd ../backend
DOCUMIND_STATIC_DIR=../frontend/dist/documind-web/browser .venv/bin/python -m uvicorn documind.main:create_app --factory --port 8000
```

On Windows PowerShell set the variable with `$env:DOCUMIND_STATIC_DIR='..\frontend\dist\documind-web\browser'`
and use `.venv\Scripts\python`. Open `http://localhost:8000`.

## Checks

```bash
cd backend
.venv/Scripts/python -m pytest
.venv/Scripts/ruff check .
.venv/Scripts/mypy
```

```bash
cd frontend
npm test
npm run format:check
npm run build
npx playwright install chromium   # once
npm run e2e                       # builds, starts the backend, runs browser tests
```

## Continuous integration

`.github/workflows/ci.yml` runs on every push to `main` and every pull request: backend lint,
formatting, strict type checks and tests on Python 3.12 and 3.14; frontend formatting, unit tests
and production build; and the end-to-end suite in Chromium against the backend serving the build.
No step needs network access to an AI provider.
