# Phase 8 report — Automated testing and CI

Date: 2026-10-26

## Built

`.github/workflows/ci.yml`, run on every push to `main`, every pull request and on demand, with
read-only permissions and superseded runs cancelled:

| Job | Steps |
|---|---|
| **Backend · Python 3.12 and 3.14** (matrix) | install with `constraints.txt` → `ruff check` → `ruff format --check` → `mypy` (strict) → `pytest` |
| **Frontend** (Node 22.14.0) | `npm ci` → Prettier check (app, e2e, config) → unit/component tests → production build |
| **End to end** (Python 3.14 + Node 22.14.0) | backend venv → `npm ci` → Playwright Chromium with system dependencies → `npm run e2e` → report uploaded as an artifact when it fails |

Python 3.12 is in the matrix because `pyproject.toml` accepts it but development has only used
3.14; until CI runs, 3.12 support is unverified.

## Verification

| Check | Result |
|---|---|
| Workflow syntax | Parsed with PyYAML; three jobs and their steps as intended. Not yet validated by GitHub. |
| Clean-checkout rehearsal (Windows, CPython 3.14.3, Node 22.14.0) | **Passed.** Fresh `git clone` of commit `bf7faf4` (no untracked or ignored files), new venv from `constraints.txt`, `npm ci`: ruff, format and mypy clean; **265** backend tests; Prettier clean; **62** frontend tests; production build; **8** end-to-end tests. Proves the repository alone is enough to build and test — on Windows, not yet on Linux. |
| First run on GitHub | Repository [moeletsimelamu/documind](https://github.com/moeletsimelamu/documind) created by the owner; `main` pushed on 2026-10-26. [Run 40300902498](https://github.com/moeletsimelamu/documind/actions/runs/40300902498) on `6b1d155`: **all four jobs passed** on Linux, including Python 3.12 (first time tested) and the end-to-end suite. |
| Deliberately failing change | The workflow now runs on pushes to every branch (it first ran only on `main` and pull requests, so a pushed branch triggered nothing). A throwaway branch disabling citation validation — a security-relevant regression in code, not a broken test — produced [run 40310846964](https://github.com/moeletsimelamu/documind/actions/runs/40310846964): **failed** at the backend *Tests* step on Python 3.12 and 3.14, while lint, formatting and type checks passed, and the frontend and end-to-end jobs (which do not exercise answer validation) passed. The branch was then deleted; the failed run remains in the Actions history. |

## Not done yet

- Docker image build in CI — added with the Dockerfile in Phase 10 (see the Phase 10 report).
