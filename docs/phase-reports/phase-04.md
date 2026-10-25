# Phase 4 report — Search and retrieval

Date: 2026-10-25

## Built

| Piece | What it does |
|---|---|
| `retrieval.py` | Query parsing (words, quoted phrases, stop words, 32-term cap), safe FTS5 MATCH expressions, BM25-ranked search over `ready` documents with optional document scope, totals, FTS5 `highlight()` → offsets, excerpt windows |
| `api/search.py` | `GET /api/search` (query length and empty-query errors, `limit` ≤ 50, repeatable `document_id`) and `GET /api/chunks/{id}` for opening a passage |
| `tests/eval/` | Four fictional documents, 30 labelled questions, `run_eval.py` reporting hit@k and MRR |
| `tests/test_retrieval_eval.py` | Fails the build if retrieval quality drops below the recorded baseline |

## Verification (2026-10-25, Windows 11, CPython 3.14.3)

| Check | Result |
|---|---|
| `pytest` | **199 passed** (152 from earlier phases + retrieval 32, search API 14, evaluation guard 1) |
| `ruff check`, `ruff format --check`, `mypy` (strict) | clean |
| Evaluation | Keyword questions: hit@1 95%, hit@5 100%. Paraphrased questions: hit@1 33%, hit@5 56%. Overall hit@5 87%, MRR@5 0.81. Details and every miss in ARCHITECTURE.md §7. |
| Real server | After uploading two sample files, "What did the board approve for the budget?" searched for `board, approve, budget` and returned the meeting notes (lines 1–7) with *Board, Budget, board, approved, budget* highlighted, in 10–15 ms. `NEAR(currency risk) OR "supplier` was searched as plain words (4 passages). `???` returned `422 empty_query`. The access log recorded `GET /api/search -> 200` without the query. |

Tests cover: stop words and lower-casing; stop-word-only queries; phrases; de-duplication; 10
hostile inputs (FTS5 operators, column filters, unbalanced quotes, SQL fragments) producing only
quoted alphanumeric terms and executing without error; empty queries; the 32-term cap; highlight
parsing; excerpt windows keeping highlight offsets valid; ranking with source identity and page;
stemming and accent folding; phrase adjacency; only `ready` documents searchable; document scoping;
limit vs totals; no matches; line ranges for text files; HTML in documents returned as plain text;
deleted documents vanishing from results; chunk lookup and 404.

## Decisions

- Highlights come from FTS5 itself rather than re-implementing the Porter stemmer (D19).
- No synonym lists, embeddings or chunk overlap for now (D20). The evaluation shows keyword search
  is reliable when questions share vocabulary with the text and weak when they do not; that limit
  will be stated in the UI ("Matches words and word forms, not meaning") and in the README.

## Known limitations

- Paraphrased questions are often missed (56% hit@5 on this set).
- The evaluation set is small and written by the same author as the code; treat the numbers as
  an illustration of behaviour, not a benchmark.
- English stop words only; other languages are searched without stop-word removal (which works,
  just with noisier ranking).
- Totals are computed with a second query; fine at this scale (single user, thousands of chunks).
