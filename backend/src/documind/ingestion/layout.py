"""Layout clean-up for the text of PDF pages.

pypdf returns each page as lines in reading order, without paragraph information and with the
page's running header, footer and page number mixed into the text. Indexed as they are, a header
such as "Digital Identity Guidelines" matches a search on every page, and the reader shows each
page as one block. ``clean_pdf_pages`` works on a whole document, because running headers can only
be recognised by repetition:

- Running headers and footers are removed: lines among the first or last few of a page that
  recur, ignoring a page number at either end of the line, near the top or bottom of many pages.
  Lines that differ in any other number ("Sentence 3 …", "Total 1,250 …") are not the same line,
  so pages generated from a template keep their text.
- Page numbers are removed from the very top or bottom of a page when they are written as such
  ("Page 4 of 9", roman numerals) or, for bare numbers, when they rise with the page index on
  many pages. A number at the bottom of a table does not, so it stays.
- Paragraph boundaries become blank lines: before list items, around headings, and after a line
  that ends a sentence well short of the page's usual line length.
- Dot leaders in tables of contents are shortened to an ellipsis.
- Words split across lines with a hyphen are rejoined; the hyphen is kept when the word is
  hyphenated elsewhere in the document or already contains one ("left-to-\\nright").

Every removal is limited to whole lines at the edges of a page, at most ``EDGE_LINES`` at each
end, so body text is never cut.
"""

import math
import re
from collections import Counter

EDGE_LINES = 5  # lines at each end of a page that may belong to a running header or footer
MIN_REPEATS = 3
MIN_REPEAT_SHARE = 0.3  # share of pages on which an edge line must recur to count as running
MAX_RUNNING_LINE_CHARS = 150

# For character classes; the hyphen is escaped so that it never forms a range.
_DASHES = r"\-" + chr(0x2013) + chr(0x2014)  # hyphen, en dash, em dash
_CLOSERS = "'\"" + chr(0x2019) + chr(0x201D) + ")"  # quotes or a bracket after a full stop
_EDGE_NUMBER = re.compile(r"^\d{1,4}\s+|\s+\d{1,4}$")  # "Annual report 2025 · 14"
_PAGE_LABEL = re.compile(
    rf"^(?:(page)\s+)?[{_DASHES}]?\s*(\d{{1,4}})\s*[{_DASHES}]?(?:\s*(?:of|/)\s*\d{{1,4}})?$",
    re.IGNORECASE,
)
_ROMAN = re.compile(r"^(?=[ivxlc])c{0,3}(?:xc|xl|l?x{0,3})(?:ix|iv|v?i{0,3})$", re.IGNORECASE)
_LIST_ITEM = re.compile(
    rf"^(?:[•◦▪▫●○■□➢►▶✓✔*·{_DASHES}]\s|\(?(?:\d{{1,2}}|[a-z]|[ivx]{{1,4}})[.)]\s)"
)
_NUMBERED_HEADING = re.compile(r"^\d+(?:\.\d+)+\.?\s+[A-Z]|^[A-Z]\.\d+(?:\.\d+)*\.?\s+[A-Z]")
_SECTION_NUMBER = re.compile(r"^\d+(?:\.\d+)*\.?\s+")
_DOT_LEADER = re.compile(r"(?:\s*\.){4,}\s*")
_ENDS_SENTENCE = re.compile(rf"[.!?:][{_CLOSERS}]?$")
_ENDS_CLAUSE = re.compile(rf"[.,;:!?{_CLOSERS}]$")
_HYPHEN_BREAK = re.compile(r"(\w+(?:-\w+)*)-\n([a-z]\w*)")
_HYPHENATED_WORD = re.compile(r"\b[A-Za-z]+(?:-[A-Za-z]+)+\b")


def clean_pdf_pages(pages: list[str]) -> list[str]:
    """Clean the normalised text of every page of one PDF (see the module docstring)."""
    lines_per_page = [page.split("\n") for page in pages]
    # Running lines first, so that a page number below a header becomes the outermost line.
    lines_per_page = _remove_running_lines(lines_per_page)
    lines_per_page = _remove_page_numbers(lines_per_page)
    structured = [_structure(lines) for lines in lines_per_page]
    hyphenated = {word.lower() for page in structured for word in _HYPHENATED_WORD.findall(page)}
    return [_join_hyphenated(page, hyphenated) for page in structured]


def _signature(line: str) -> str:
    return _EDGE_NUMBER.sub(" # ", line.strip().lower()).strip()


def _edge_indexes(lines: list[str]) -> list[int]:
    """The first and last few non-empty lines: up to a third of the page's lines at each end."""
    filled = [i for i, line in enumerate(lines) if line.strip()]
    size = min(EDGE_LINES, max(2, len(filled) // 3))
    return sorted(set(filled[:size] + filled[-size:]))


def _is_page_label(line: str) -> bool:
    return bool(_PAGE_LABEL.match(line) or _ROMAN.match(line))


def _remove_running_lines(lines_per_page: list[list[str]]) -> list[list[str]]:
    counts: Counter[str] = Counter()
    for lines in lines_per_page:
        counts.update(
            {
                _signature(lines[i])
                for i in _edge_indexes(lines)
                if len(lines[i]) <= MAX_RUNNING_LINE_CHARS
                and not _is_page_label(lines[i].strip())  # handled by _remove_page_numbers
            }
        )
    needed = max(MIN_REPEATS, math.ceil(MIN_REPEAT_SHARE * len(lines_per_page)))
    running = {signature for signature, count in counts.items() if count >= needed}
    return [_blank_edges(lines, running) for lines in lines_per_page]


def _blank_edges(lines: list[str], running: set[str]) -> list[str]:
    edges = set(_edge_indexes(lines))
    return [
        "" if i in edges and _signature(line) in running else line for i, line in enumerate(lines)
    ]


def _remove_page_numbers(lines_per_page: list[list[str]]) -> list[list[str]]:
    candidates: list[tuple[int, int, int | None]] = []  # page, line, printed number - page index
    romans: list[tuple[int, int]] = []
    for page_index, lines in enumerate(lines_per_page):
        filled = [i for i, line in enumerate(lines) if line.strip()]
        for i in sorted({filled[0], filled[-1]}) if filled else []:
            text = lines[i].strip()
            label = _PAGE_LABEL.match(text)
            if label:
                explicit = label.group(1) is not None  # "Page 4", "page 4 of 9"
                offset = None if explicit else int(label.group(2)) - page_index
                candidates.append((page_index, i, offset))
            elif _ROMAN.match(text):  # front matter: i, ii, iii …
                romans.append((page_index, i))
    offsets = Counter(offset for _, _, offset in candidates if offset is not None)
    needed = max(2, math.ceil(MIN_REPEAT_SHARE * len(lines_per_page)))
    consistent = {offset for offset, count in offsets.items() if count >= needed}
    result = [list(lines) for lines in lines_per_page]
    for page_index, i, offset in candidates:
        if offset is None or offset in consistent:
            result[page_index][i] = ""
    if len(romans) >= 2:  # one lone "C" or "I" at the end of a page is more likely content
        for page_index, i in romans:
            result[page_index][i] = ""
    return result


def _structure(lines: list[str]) -> str:
    """Join the page's lines, marking paragraph boundaries with a blank line."""
    lines = [
        _DOT_LEADER.sub(" … ", line).strip() if _DOT_LEADER.search(line) else line for line in lines
    ]
    filled = [line for line in lines if line.strip()]
    if not filled:
        return ""
    lengths = sorted(len(line) for line in filled)
    usual = lengths[min(len(lengths) - 1, int(len(lengths) * 0.75))]

    out: list[str] = []
    previous = ""
    for index, line in enumerate(lines):
        if not line.strip():
            if out and out[-1] != "":
                out.append("")
            previous = ""
            continue
        following = next((nxt for nxt in lines[index + 1 :] if nxt.strip()), "")
        heading = _is_heading(line, previous, following, usual)
        if out and out[-1] != "" and (heading or _LIST_ITEM.match(line) or " … " in line):
            out.append("")
        out.append(line)
        ends_paragraph = _ENDS_SENTENCE.search(line) and len(line) < 0.8 * usual
        if heading or ends_paragraph:
            out.append("")
        previous = line
    while out and out[-1] == "":
        out.pop()
    return "\n".join(out)


def _is_heading(line: str, previous: str, following: str, usual: int) -> bool:
    if (
        _NUMBERED_HEADING.match(line)
        and len(line) < min(100, 0.8 * usual)
        and not _ENDS_SENTENCE.search(line)
    ):
        return True
    return (
        len(line) <= 80
        and len(line) < 0.7 * usual
        and _SECTION_NUMBER.sub("", line)[:1].isupper()
        and not _ENDS_CLAUSE.search(line)
        and (not previous or bool(_ENDS_SENTENCE.search(previous)))
        and following[:1].isupper()
    )


def _join_hyphenated(text: str, hyphenated: set[str]) -> str:
    def join(match: re.Match[str]) -> str:
        first, second = match.group(1), match.group(2)
        keep = "-" in first or f"{first}-{second}".lower() in hyphenated
        return f"{first}-{second}" if keep else f"{first}{second}"

    return _HYPHEN_BREAK.sub(join, text)
