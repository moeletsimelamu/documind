# DocuMind — Deployment

DocuMind is a **single-user application meant to run on your own machine**. It has no user
accounts: anyone who can reach it can read and delete every document. There is **no public
deployment** of DocuMind, and none is recommended without the extra measures in §5.

## 1. Ways to run it

| Mode | For | Command (from the repository root unless noted) |
|---|---|---|
| Development | Working on the code | backend: `uvicorn documind.main:create_app --factory --port 8000` (in `backend/`); frontend: `npm start` (in `frontend/`, port 4200, proxies `/api`) |
| One process | Using it without Docker | `npm run build` in `frontend/`, then start the backend with `DOCUMIND_STATIC_DIR=../frontend/dist/documind-web/browser` and open `http://localhost:8000` |
| Container | Using it with Docker | see §2 |

Setup of the Python and Node environments is in the README.

## 2. Container

The `Dockerfile` builds the frontend with Node 22.14.0, then installs the backend into
`python:3.14.9-slim-trixie` with the exact versions in `backend/constraints.txt`. The FastAPI
process serves both the API and the built app.

```bash
docker build -t documind .
docker run -d --name documind \
  -p 127.0.0.1:8000:8000 \
  -v documind-data:/data \
  documind
```

Open `http://localhost:8000`.

- **Publish on loopback only** (`127.0.0.1:8000:8000`). Inside the container the server listens on
  all interfaces because it has to; the host mapping decides who can reach it.
- **Data** — the SQLite database and uploaded files — lives in the `/data` volume, never in the
  image. Removing the container keeps the volume; `docker volume rm documind-data` deletes
  everything.
- The process runs as an unprivileged user (uid 10001) that owns only `/data`.
- Swagger UI is off in the image (`DOCUMIND_API_DOCS=false`).
- A `HEALTHCHECK` calls `/api/ready` (database, search index and storage).
- **AI answers** are off unless configured at run time, for example with an env file that is
  never committed or built into the image:

  ```bash
  docker run -d --name documind -p 127.0.0.1:8000:8000 -v documind-data:/data \
    --env-file documind.env documind
  ```

  `documind.env` contains `DOCUMIND_LLM_MODEL`, `DOCUMIND_LLM_BASE_URL` and, for hosted
  providers, `DOCUMIND_LLM_API_KEY`. To use a model server on the host (e.g. Ollama), point the base
  URL at `http://host.docker.internal:11434/v1` (Docker Desktop) or the host's address.

**What keeps secrets and documents out of the image:** `.dockerignore` excludes `.env*`, the data
directory, databases, virtual environments, `node_modules`, tests and `.git`; the Dockerfile copies
only `backend/src`, the two dependency files, and the built frontend. CI checks every image: it
runs as uid 10001, `/data` is empty, and no `.env*` file exists anywhere in the file system.

**How the image is verified.** Docker is not installed on the development machine, so the image is
built and tested **only in CI** (`docker` job): build, the hygiene checks above, then
`scripts/smoke-test.sh` against the running container — readiness, app shell and client routes,
Swagger off, foreign `Host` refused, upload → processing in the isolated worker → search → Ask →
delete. The same script was run locally against the backend configured like the container.

## 3. Configuration

All settings are environment variables prefixed `DOCUMIND_`; the full list with defaults is in
ARCHITECTURE.md §11 and `.env.example`. The ones that matter for deployment:

| Variable | Default | Notes |
|---|---|---|
| `DOCUMIND_DATA_DIR` | `./data` (`/data` in the image) | Database and uploads |
| `DOCUMIND_STATIC_DIR` | unset (`/app/static` in the image) | Built frontend to serve |
| `DOCUMIND_ALLOWED_HOSTS` | `["localhost","127.0.0.1","[::1]"]` | Must include the host name used in the browser; protects against DNS rebinding |
| `DOCUMIND_API_DOCS` | `true` (`false` in the image) | Swagger UI at `/api/docs` |
| `DOCUMIND_MAX_UPLOAD_MB`, `DOCUMIND_MAX_PDF_PAGES`, `DOCUMIND_EXTRACTION_TIMEOUT_SECONDS`, `DOCUMIND_EXTRACTION_MEMORY_LIMIT_MB` | 20, 500, 120, 1024 | Resource limits; the memory limit applies on Linux/macOS only |
| `DOCUMIND_LLM_MODEL`, `DOCUMIND_LLM_BASE_URL`, `DOCUMIND_LLM_API_KEY`, `DOCUMIND_LLM_TIMEOUT_SECONDS` | unset, OpenAI, unset, 30 | AI answers; unset model = off |

## 4. Operations

- **Logs** go to standard output (`docker logs documind`): request method, path, status and
  duration with a request ID, processing outcomes by document ID, provider status codes. They do
  not contain document text, questions, search terms, file names or keys.
- **Backup:** stop the container (or the server), then copy the data volume/directory — it holds
  `documind.db` (plus `-wal`/`-shm` files while running) and `uploads/`. Copying while the server
  runs can capture an inconsistent database.
- **Upgrade:** rebuild the image and start a new container with the same volume. The schema
  version is checked at start-up; a database from a newer version is refused rather than modified.
- **Restart behaviour:** documents that were being processed when the server stopped are marked
  `failed` / `interrupted` (delete and upload again); stray files are removed.

## 5. Putting it on a network (not done; requirements if you do)

DocuMind does not implement authentication, so serving it beyond your own machine needs, at
minimum:

1. an authenticating reverse proxy (single sign-on or basic auth) in front of it;
2. TLS at that proxy;
3. `DOCUMIND_ALLOWED_HOSTS` set to the public host name;
4. request-rate and body-size limits at the proxy;
5. backups of the data volume;
6. accepting that every signed-in user sees every document — there is no per-user isolation.

## 6. Screenshots

The README screenshots are of the real application, captured with
`frontend/scripts/capture-screenshots.mjs` against a server holding the fictional documents from
`backend/tests/eval/dataset.py` and an image-only PDF made with `tests/pdf_factory.py`. AI answers
were off, so no screenshot shows a generated answer.
