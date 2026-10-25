# Phase 1 report — Discovery and architecture

Date: 2026-10-25

## What was inspected

- **Workspace:** the session started in `Desktop/OpsHub`, the existing OpsHub repository (.NET +
  Angular, remote `github.com/moeletsimelamu/opshub`, clean working tree). DocuMind is a separate
  product, so it gets its own folder: `Desktop/DocuMind` (new git repository, branch `main`).
- **Toolchain:** Python 3.14.3 (only interpreter installed), pip 25.3, Node 22.14.0, npm 10.9.2,
  Angular CLI 21.2.13 (global), git 2.54. **Not installed:** Docker, GitHub CLI, uv.
- **SQLite:** Python's bundled SQLite is 3.50.4 and an FTS5 table with the `porter unicode61`
  tokenizer was created successfully.
- **Dependency compatibility:** the full backend set (FastAPI, Uvicorn, Pydantic, pydantic-settings,
  SQLAlchemy, pypdf, python-multipart, pytest, httpx, ruff, mypy) resolved with
  `pip install --dry-run --only-binary=:all:` — every compiled package has a `cp314` Windows wheel.
- **Angular:** latest is 22.2.3, but its engines field requires Node `^22.22.3 || ^24.15.0`. The
  installed Node 22.14.0 does not qualify, so Angular **21.2.x (LTS)** is selected.
- **Git identity:** OpsHub's *local* config is `Moeletsi Melamu <moeletsimelamu03@gmail.com>`;
  the *global* config is `Junior Melamu <u22715895@up.ac.za>`. A new repository would inherit the
  global identity, so this needs confirming before the first commit.
- **OpsHub design** was read only to make sure DocuMind looks different (different palette,
  typography and navigation pattern).

## Deliverables

- `docs/ARCHITECTURE.md` — trust model, components, versions, data model, pipeline, retrieval,
  Q&A grounding and citation validation, API contract, configuration, security controls, testing.
- `docs/DESIGN.md` — users and workflows, visual direction, measured colour contrast, typography,
  layouts for each page, the visual language separating sources from generated text, components,
  accessibility targets.
- `docs/PLAN.md` — phase plan with "done when" criteria and the decision log.

No application code was written in this phase.

## Risks

| Risk | Mitigation |
|---|---|
| Docker not installed locally | Dockerfile is built and checked in CI; documented as not verified locally unless Docker is installed. |
| Python 3.14 is recent | All wheels verified; CI and the image use 3.14 to match. |
| pypdf slowness on hostile PDFs | Page/size limits; decide on a subprocess timeout in Phase 3 after measuring. |
| Keyword search misses paraphrased questions | Measured in Phase 4 evaluation; documented; semantic re-ranking only if justified. |
| Prompt injection via documents | Structural defences (no tools, validated citations, DB-sourced excerpts) + delimiting; limits documented. |
| Real-key LLM test needs a paid key | All tests use fakes; a live check runs only if a key is provided. |

## Decisions taken with the owner

1. **Git identity:** `Moeletsi Melamu <moeletsimelamu03@gmail.com>`, set in DocuMind's local git config.
2. **LLM provider:** an OpenAI-compatible chat API (hosted OpenAI or a local server such as
   Ollama), called with httpx. The Anthropic SDK originally proposed is not used.
