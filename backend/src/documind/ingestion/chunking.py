"""Text normalisation and chunking.

Chunks are built from whole lines and break preferably at paragraph boundaries. PDF chunks never
cross a page; text-file chunks record the line range they came from. Nothing is dropped: the
chunks of a document contain every non-whitespace character of its normalised text, in order.
"""

import re
import unicodedata
from collections.abc import Callable
from dataclasses import dataclass

CHUNK_TARGET_CHARS = 1000
CHUNK_MAX_CHARS = 1600

_SENTENCE_END = re.compile(r"(?<=[.!?])\s+")
_SPACES = re.compile(r"[ \t]+")


def normalize_text(text: str) -> str:
    """Make extracted text consistent for indexing and display.

    - Unicode NFKC (e.g. the "ﬁ" ligature becomes "fi", non-breaking spaces become spaces).
    - Line endings become ``\\n``; other control characters become spaces; NUL is removed.
    - Runs of spaces collapse; trailing spaces are removed. Line breaks are kept, so line numbers
      in text files stay correct.

    PDF pages are cleaned further, as one document, by ``layout.clean_pdf_pages``.
    """
    text = text.replace("\r\n", "\n").replace("\r", "\n").replace("\x00", "")
    text = unicodedata.normalize("NFKC", text)
    text = "".join(ch if ch == "\n" or unicodedata.category(ch) != "Cc" else " " for ch in text)
    text = text.replace("­", "")  # soft hyphen
    lines = [_SPACES.sub(" ", line).strip() for line in text.split("\n")]
    return "\n".join(lines)


@dataclass(frozen=True)
class TextChunk:
    text: str
    first_line: int
    last_line: int


@dataclass(frozen=True)
class _Piece:
    line: int
    text: str
    starts_paragraph: bool
    continues_line: bool


def _split_long(text: str, maximum: int) -> list[str]:
    """Split text longer than ``maximum`` at sentence ends, then spaces, then anywhere."""
    if len(text) <= maximum:
        return [text]
    parts: list[str] = []
    for sentence in _SENTENCE_END.split(text):
        tokens = [sentence] if len(sentence) <= maximum else sentence.split(" ")
        for token in tokens:
            for start in range(0, len(token), maximum):
                piece = token[start : start + maximum]
                if parts and len(parts[-1]) + 1 + len(piece) <= maximum:
                    parts[-1] = f"{parts[-1]} {piece}"
                else:
                    parts.append(piece)
    return [p for p in parts if p]


def chunk_lines(
    text: str,
    *,
    joiner: str,
    target: int = CHUNK_TARGET_CHARS,
    maximum: int = CHUNK_MAX_CHARS,
) -> list[TextChunk]:
    """Pack the lines of ``text`` into chunks of about ``target`` characters.

    ``joiner`` joins consecutive lines of one paragraph: a space for PDF text (whose line breaks
    are only visual), a newline for text files. Paragraphs are separated by a blank line.

    A paragraph that does not fit in the current chunk starts a new one, unless the current chunk
    is still small (for example just a heading). Inside a long paragraph, chunks break at the
    first line boundary past ``target``. No chunk exceeds ``maximum``.
    """
    paragraphs: list[list[_Piece]] = []
    blank_before = True
    for number, line in enumerate(text.split("\n"), start=1):
        if not line.strip():
            blank_before = True
            continue
        if blank_before:
            paragraphs.append([])
        for index, part in enumerate(_split_long(line.strip(), target)):
            paragraphs[-1].append(
                _Piece(
                    line=number,
                    text=part,
                    starts_paragraph=blank_before and index == 0 and len(paragraphs) > 1,
                    continues_line=index > 0,
                )
            )
        blank_before = False

    def separator(piece: _Piece) -> str:
        if piece.continues_line:
            return " "
        return "\n\n" if piece.starts_paragraph else joiner

    min_fill = target // 2
    chunks: list[TextChunk] = []
    current: list[_Piece] = []
    size = 0
    for paragraph in paragraphs:
        length = len(_build(paragraph, separator).text)
        if current and size + 2 + length > target and size >= min_fill:
            chunks.append(_build(current, separator))
            current, size = [], 0
        for piece in paragraph:
            if current:
                projected = size + len(separator(piece)) + len(piece.text)
                if projected > maximum or (projected > target and size >= min_fill):
                    chunks.append(_build(current, separator))
                    current, size = [], 0
            if current:
                size += len(separator(piece))
            current.append(piece)
            size += len(piece.text)
    if current:
        chunks.append(_build(current, separator))
    return chunks


def _build(pieces: list[_Piece], separator: Callable[[_Piece], str]) -> TextChunk:
    text = pieces[0].text + "".join(separator(p) + p.text for p in pieces[1:])
    return TextChunk(text=text, first_line=pieces[0].line, last_line=pieces[-1].line)
