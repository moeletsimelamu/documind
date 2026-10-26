# Phase 6 report — Optional AI answers

Date: 2026-10-26

## Built

| Piece | What it does |
|---|---|
| `answering/provider.py` | `LanguageModel` protocol and provider errors with safe, user-facing messages |
| `answering/openai_compatible.py` | httpx2 client for any OpenAI-compatible `/chat/completions` endpoint: JSON-object replies, temperature 0, bounded output, status → error mapping, logs status and timing only |
| `answering/prompt.py` | Fixed system prompt (sources are untrusted data; cite `[S<n>]`; say when insufficient); user message with escaped `<source>` elements; strict reply parsing |
| `answering/service.py` | Retrieval → model → `ground_reply` validation; fallback to passages on provider failure; context budget |
| `api/ask.py`, `schemas.py`, `config` | `answer`, `cited`, `generation_error`, `model` in responses; `llm_model` (name only) in client config; `DOCUMIND_LLM_MAX_OUTPUT_TOKENS` |
| Frontend Ask page | Generated answer with citation chips, Sources column (sticky on wide screens), uncited sources dimmed, provider-failure banner, "closest passages" for insufficient evidence, AI-on notice naming the model and what is sent |

## Verification (2026-10-26)

| Check | Result |
|---|---|
| Backend `pytest` / ruff / mypy | **250 passed**; clean |
| Frontend `ng test` / prettier / production build | **62 passed**; clean; no budget warnings |
| Mutation check | Accepting every `[S…]` id instead of only retrieved ones made 5 tests fail (invented, grouped and only-invalid citations, the injection test, the endpoint test). Reverted. |
| Browser, with a local OpenAI-compatible **test double** (quotes passages; not an AI) and the real backend client | Generated answer with S1/S2 chips and Sources column at 1280 px; marker selects, focuses and reveals the source without leaving the answer; 375 px stacked layout, no overflow, marker scrolls to the source; timeout after the configured 5 s → banner + passages; invented `[S9]` answer never shown → insufficient evidence; model "insufficient" → closest passages; non-JSON reply → "not in the expected format" banner. Server log: status codes, timings and outcome codes only. |

Tests cover: the system prompt's rules; numbering and locations of sources; escaping that stops a
passage from closing its `<source>` or forging another; reply parsing (fences, wrong shapes); the
request sent to the provider (URL, auth header only with a key, model, messages, temperature,
`max_tokens`, `response_format`); eleven failure mappings (timeout, unreachable, 401, 403, 404,
429, 400, 503, HTML, no choices, null content); no key, question, prompt or answer in logs;
citation grounding (valid kept in order, invalid removed from text and list, grouped markers,
listed-only ids); flows (grounded answer, model not called without passages, insufficient
respected, uncited or only-invalid-cited answers discarded, timeout and non-JSON fall back with the
reason, no model → retrieval-only, context budget); a prompt-injection document whose instructions
a compliant fake model follows; frontend splitting of answers into citation parts, the generated
view, source selection and focus, failure banner, closest passages, AI-on notice.

## Defects found and fixed during the phase

1. **Selecting a source scrolled the whole page** (scrollY 0 → 407) instead of the Sources column,
   moving the answer away. Now only the column scrolls; if the column extends below the window, the
   answer row is brought to the top first so both are on screen (measured).
2. **Space before the full stop after citation chips** ("results S1 ."), from whitespace inside the
   button that Angular collapses to a space and Prettier re-adds. The label is now bound with
   `[textContent]`; a test asserts the exact text.
3. The HTTP client library logged every request URL at INFO; its logger is now WARNING.

## Not verified

- **No run against a real language model.** No local model server (Ollama, LM Studio) is installed
  and no API key was available; using a paid service was out of scope. The client follows the
  OpenAI chat-completions format and was exercised against a test double. A real run should check:
  that the chosen model returns valid JSON with `response_format: json_object` (some local servers
  ignore or reject it), citation habits, and latency against the 30 s default timeout.
- Answer quality is not measured; the retrieval evaluation (Phase 4) bounds what any model can do.
