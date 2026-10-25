"""Keyword search over indexed chunks with SQLite FTS5, ranked by BM25.

This is lexical retrieval: it matches words and their stemmed forms ("deliveries" matches
"delivery"), not meaning. User input never reaches FTS5's query syntax directly: the application
extracts words itself and quotes every term, so operators such as NEAR, *, -, ^ or column filters
in a query are searched as ordinary words.
"""

import re
from dataclasses import dataclass, field

from sqlalchemy import bindparam, text
from sqlalchemy.orm import Session

# Matches FTS5's unicode61 tokenizer closely enough: runs of letters and digits.
_TOKEN = re.compile(r"[^\W_]+")
_PHRASE = re.compile(r'"([^"]*)"')
_HIGHLIGHT_OPEN = "\x01"
_HIGHLIGHT_CLOSE = "\x02"

MAX_QUERY_TERMS = 32
EXCERPT_CHARS = 320

# Common words dropped from queries (unless the query has nothing else).
_STOP_WORDS_TEXT = """
    a about above after again all also am an and any are as at be because been before being
    below between both but by can could did do does doing down during each few for from further
    had has have having he her here hers him his how i if in into is it its itself just me more
    most my no nor not of off on once only or other our ours out over own same she should so some
    such than that the their theirs them then there these they this those through to too under
    until up very was we were what when where which while who whom why will with would you your
    yours tell show give find please many much
"""
STOP_WORDS = frozenset(_STOP_WORDS_TEXT.split())


class EmptyQueryError(ValueError):
    pass


@dataclass(frozen=True)
class ParsedQuery:
    terms: list[str]
    phrases: list[list[str]]

    def match_expression(self) -> str:
        """An FTS5 MATCH expression where every term and phrase is a quoted string."""
        parts = [f'"{" ".join(words)}"' for words in self.phrases]
        parts += [f'"{term}"' for term in self.terms]
        return " OR ".join(parts)

    @property
    def searched_for(self) -> list[str]:
        return [" ".join(words) for words in self.phrases] + self.terms


def parse_query(raw: str) -> ParsedQuery:
    """Words and "quoted phrases" from user input. Raises EmptyQueryError if there are none."""
    phrases: list[list[str]] = []
    for match in _PHRASE.finditer(raw):
        words = [w.lower() for w in _TOKEN.findall(match.group(1))]
        if words:
            phrases.append(words)
    remainder = _PHRASE.sub(" ", raw)
    words = [w.lower() for w in _TOKEN.findall(remainder)]
    terms = [w for w in words if w not in STOP_WORDS] or words  # "to be or not to be"
    unique_terms = list(dict.fromkeys(terms))[:MAX_QUERY_TERMS]
    unique_phrases = list({tuple(p): p for p in phrases}.values())[:MAX_QUERY_TERMS]
    if not unique_terms and not unique_phrases:
        raise EmptyQueryError("Enter at least one word to search for.")
    return ParsedQuery(terms=unique_terms, phrases=unique_phrases)


@dataclass(frozen=True)
class Passage:
    chunk_id: int
    document_id: str
    document_name: str
    file_type: str
    ordinal: int
    page: int | None
    line_start: int | None
    line_end: int | None
    text: str
    # BM25 from FTS5: lower is better. Internal; not part of the public API.
    score: float
    highlights: list[tuple[int, int]] = field(default_factory=list)

    def excerpt(self, width: int = EXCERPT_CHARS) -> "Excerpt":
        return make_excerpt(self.text, self.highlights, width)


@dataclass(frozen=True)
class Excerpt:
    text: str
    highlights: list[tuple[int, int]]
    starts_mid_text: bool
    ends_mid_text: bool


@dataclass(frozen=True)
class SearchResult:
    query: ParsedQuery
    passages: list[Passage]
    total_passages: int
    total_documents: int


def split_highlights(marked: str) -> tuple[str, list[tuple[int, int]]]:
    """Turn FTS5 highlight() output into plain text plus [start, end) character offsets."""
    plain: list[str] = []
    spans: list[tuple[int, int]] = []
    position = 0
    start: int | None = None
    for ch in marked:
        if ch == _HIGHLIGHT_OPEN:
            start = position
        elif ch == _HIGHLIGHT_CLOSE:
            if start is not None and position > start:
                spans.append((start, position))
            start = None
        else:
            plain.append(ch)
            position += 1
    return "".join(plain), spans


def make_excerpt(text_: str, highlights: list[tuple[int, int]], width: int) -> Excerpt:
    """A window of about ``width`` characters containing as many highlights as possible."""
    if len(text_) <= width:
        return Excerpt(text_, list(highlights), False, False)

    best_start = 0
    if highlights:
        best_count = -1
        for anchor, _ in highlights:
            candidate = max(0, min(anchor - width // 5, len(text_) - width))
            count = sum(1 for s, e in highlights if s >= candidate and e <= candidate + width)
            if count > best_count:
                best_start, best_count = candidate, count

    start, end = best_start, min(len(text_), best_start + width)
    # Widen to whole words so the excerpt does not begin or end mid-word.
    if start > 0:
        space = text_.rfind(" ", 0, start)
        start = space + 1 if space != -1 and start - space < 30 else start
    if end < len(text_):
        space = text_.find(" ", end)
        end = space if space != -1 and space - end < 30 else end

    shifted = [(s - start, e - start) for s, e in highlights if s >= start and e <= end]
    return Excerpt(text_[start:end], shifted, start > 0, end < len(text_))


def _scope_clause(document_ids: list[str] | None) -> str:
    return " AND c.document_id IN :document_ids" if document_ids else ""


def search(
    session: Session,
    raw_query: str,
    *,
    limit: int,
    document_ids: list[str] | None = None,
) -> SearchResult:
    """Ranked passages from documents that are ``ready``, optionally limited to some documents."""
    query = parse_query(raw_query)
    params: dict[str, object] = {"match": query.match_expression(), "limit": limit}
    if document_ids:
        params["document_ids"] = document_ids
    scope = _scope_clause(document_ids)

    passages_sql = text(
        f"""
        SELECT c.id, c.document_id, d.display_name, d.file_type, c.ordinal, c.page,
               c.line_start, c.line_end,
               highlight(chunks_fts, 0, char(1), char(2)) AS marked,
               bm25(chunks_fts) AS score
        FROM chunks_fts
        JOIN chunks c ON c.id = chunks_fts.rowid
        JOIN documents d ON d.id = c.document_id
        WHERE chunks_fts MATCH :match AND d.status = 'ready'{scope}
        ORDER BY score, c.document_id, c.ordinal
        LIMIT :limit
        """  # noqa: S608 - only the fixed scope clause is interpolated; values are bound
    )
    totals_sql = text(
        f"""
        SELECT count(*), count(DISTINCT c.document_id)
        FROM chunks_fts
        JOIN chunks c ON c.id = chunks_fts.rowid
        JOIN documents d ON d.id = c.document_id
        WHERE chunks_fts MATCH :match AND d.status = 'ready'{scope}
        """  # noqa: S608 - as above
    )
    if document_ids:
        passages_sql = passages_sql.bindparams(bindparam("document_ids", expanding=True))
        totals_sql = totals_sql.bindparams(bindparam("document_ids", expanding=True))

    passages = []
    for row in session.execute(passages_sql, params):
        plain, spans = split_highlights(row.marked)
        passages.append(
            Passage(
                chunk_id=row.id,
                document_id=row.document_id,
                document_name=row.display_name,
                file_type=row.file_type,
                ordinal=row.ordinal,
                page=row.page,
                line_start=row.line_start,
                line_end=row.line_end,
                text=plain,
                score=row.score,
                highlights=spans,
            )
        )
    total_passages, total_documents = session.execute(totals_sql, params).one()
    return SearchResult(query, passages, total_passages, total_documents)
