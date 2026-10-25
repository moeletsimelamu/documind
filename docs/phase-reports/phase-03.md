# Phase 3 report — Document ingestion and indexing

Date: 2026-10-25

## Built

| Module | Responsibility |
|---|---|
| `storage.py` | `LocalFileStorage`: temp files inside the storage root, rename on commit, strict stored-name pattern + containment check before any path is built, delete that tolerates Windows file locks, start-up sweep of unreferenced files |
| `ingestion/validation.py` | Display-name sanitising, extension allow-list, PDF signature check, UTF-8 / UTF-16-BOM text decoding |
| `ingestion/extraction.py` | pypdf page-by-page extraction, encryption handling, scanned-PDF detection, page and character limits, TXT decoding; `extract_file` (worker entry point) and `extract_bytes` |
| `ingestion/isolation.py` | `run_isolated`: runs a function in a spawned process with a hard timeout, re-raises its exceptions, detects crashes via the process sentinel |
| `ingestion/chunking.py` | Normalisation (NFKC, control characters, PDF hyphen rejoining) and paragraph-aware chunking with page / line references |
| `ingestion/pipeline.py` | `accept_upload` (in-request) and `DocumentProcessor` (background processing, atomic ready/failed transitions, deleted-meanwhile handling, restart recovery) |
| `middleware.py` | `UploadSizeLimitMiddleware` (Content-Length check and byte counting); the access log now times requests up to the end of the response |
| `api/documents.py` | `GET/POST /api/documents`, `GET /api/documents/{id}`, `/chunks`, `/file`, `DELETE /api/documents/{id}` |

New dependency: `cryptography==50.0.2` (AES-encrypted PDFs). Schema: `documents.empty_page_count`.

## Verification (2026-10-25, Windows 11, CPython 3.14.3)

| Check | Result |
|---|---|
| `pytest` | **152 passed** in 75 s: Phase 2's 36 plus one new middleware test, validation 25, chunking 37 (incl. 25 randomised documents), extraction 14, isolation 5, documents API 34 |
| `ruff check`, `ruff format --check`, `mypy` (strict) | clean |
| Mutation checks | Disabling the streamed byte counter made the "no Content-Length" test fail (after the test was strengthened — see below); logging at the end of the ASGI call instead of the end of the response made the timing test fail. Both reverted. |
| Real server | Uploaded four generated files with `curl`: all returned `202 processing`, then became `ready` (3-page PDF with 1 empty page → 4 chunks; text file → 1 chunk; 500-page PDF → 2,000 chunks in 11.7 s) or `failed` (image-only PDF → `no_extractable_text`) within ~14 s. A duplicate got `409`, a `.docx` got `415`. Deleting the 500-page document returned `204`, removed its file, left 0 chunks and 0 index hits, and FTS5 `integrity-check` passed. Download returned `application/pdf` as an attachment with `nosniff`. Logs contained IDs, types, sizes and failure codes only. |

Covered by tests: path traversal and spoofed names; unsupported, fake, binary, non-UTF-8 and empty
files rejected with nothing stored; size limit by file size, by `Content-Length`, and while
streaming without one (proved to stop before the endpoint runs); duplicates (`409` with the
original's ID) and same-name different-content files; scanned, malformed, password-protected,
empty-password-encrypted, over-page-limit and over-character-limit PDFs; extraction timeout;
unexpected processing errors; page numbers and line ranges; a 5,000-line file indexed with no
characters lost; listing order and filters (LIKE wildcards literal); chunk pagination; download
headers; delete removes the row, chunks, index entries and file while leaving other documents
intact; delete during processing and mid-write; restart recovery of interrupted documents and
orphaned files, without touching unrelated files.

## Defects found and fixed during the phase

1. **Paragraphs merged across boundaries.** The first chunker only broke at a paragraph start if
   the *next line* overflowed the target, so two 600–700-character paragraphs became one chunk. It
   now looks at the whole paragraph, and splits overlong lines at the target size, not the maximum.
2. **Extraction worker could hang the processing slot forever.** Passing the file's bytes through
   process start-up blocked indefinitely when the worker died before reading them. Reproduced with
   a 2 MB payload; fixed by giving the worker the file path instead.
3. **Worker start-up crashes were only noticed at the timeout** (30 s in the reproduction). The
   parent now also waits on the process's exit sentinel: the same crash is reported in 0.4 s.
4. **A test that could not fail.** With the streamed size check disabled, the "no Content-Length"
   test still passed because the later per-file check also returns 413. The test now asserts the
   upload handler was never reached.
5. **Misleading access-log timings.** Upload requests were logged as taking 3–14 s because the
   background job ran inside the same ASGI call. The time is now taken when the response completes.

## Decisions

- Extraction runs in a separate process with a 120 s timeout (D15–D16). Measured costs and margins
  are in ARCHITECTURE.md §6.
- Interrupted documents are failed, not retried, on restart (D18).
- Empty text files are rejected at upload (`422`); damaged PDFs are accepted and fail visibly during
  processing, so the user sees the reason in the library.

## Known limitations carried forward

- No memory limit on the extraction worker (Windows has no portable mechanism); review in Phase 9.
- Starting the worker costs ~2.4 s per document on Windows. A persistent worker pool would remove
  this but needs careful handling of timeouts; not worth it yet.
- Upload bodies are spooled by python-multipart to the system temp directory before validation
  (bounded by the size limit); they are deleted when the request ends.
- Hyphen rejoining is a heuristic: a genuine compound split at a line end ("well-\nknown") is
  joined as "wellknown".
- Text-file encodings other than UTF-8/UTF-16 are rejected rather than guessed.
