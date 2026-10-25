"""Text extraction from PDF and TXT files.

``extract_file`` runs in a separate process (see ``isolation.py``). It is given the path of the
stored file rather than its contents, so starting the process never has to transfer a large
payload; everything it returns is plain picklable data.
"""

import logging
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path

from pypdf import PasswordType, PdfReader
from pypdf.errors import DependencyError

from documind.ingestion.chunking import normalize_text
from documind.ingestion.validation import TextDecodingError, decode_text

logger = logging.getLogger(__name__)

# A PDF averaging fewer non-whitespace characters per page than this is treated as scanned:
# image-only pages often carry a few characters of text (page numbers, a scanner watermark).
MIN_CHARS_PER_PAGE = 25


class ExtractionError(Exception):
    """Extraction failed for a reason the user can act on. ``message`` is safe to display."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(code, message)
        self.code = code
        self.message = message


@dataclass(frozen=True)
class ExtractionRequest:
    path: str
    file_type: str
    max_pages: int
    max_chars: int


@dataclass(frozen=True)
class ExtractedPage:
    number: int | None  # 1-based page number for PDFs, None for text files
    text: str  # normalised


@dataclass(frozen=True)
class ExtractedDocument:
    pages: list[ExtractedPage]
    page_count: int | None
    empty_page_count: int | None

    @property
    def char_count(self) -> int:
        return sum(len(page.text) for page in self.pages)


def _non_whitespace(text: str) -> int:
    return sum(1 for ch in text if not ch.isspace())


def extract_file(request: ExtractionRequest) -> ExtractedDocument:
    """Entry point for the isolated extraction process."""
    try:
        data = Path(request.path).read_bytes()
    except FileNotFoundError as exc:
        raise ExtractionError(
            "file_missing",
            "The uploaded file is missing from storage. Delete this document and upload the "
            "file again.",
        ) from exc
    return extract_bytes(
        data, request.file_type, max_pages=request.max_pages, max_chars=request.max_chars
    )


def extract_bytes(
    data: bytes, file_type: str, *, max_pages: int, max_chars: int
) -> ExtractedDocument:
    if file_type == "pdf":
        document = _extract_pdf(data, max_pages)
    elif file_type == "txt":
        document = _extract_txt(data)
    else:
        raise ExtractionError("unsupported_file_type", "This file type is not supported.")

    if document.char_count > max_chars:
        raise ExtractionError(
            "too_large",
            f"The document contains more than {max_chars:,} characters of text, "
            "which is the limit.",
        )
    return document


def _extract_txt(data: bytes) -> ExtractedDocument:
    try:
        text = normalize_text(decode_text(data))
    except TextDecodingError as exc:
        raise ExtractionError("unreadable_text", str(exc)) from exc
    if _non_whitespace(text) == 0:
        raise ExtractionError("no_extractable_text", "The file contains no text.")
    return ExtractedDocument(
        pages=[ExtractedPage(number=None, text=text)], page_count=None, empty_page_count=None
    )


def _extract_pdf(data: bytes, max_pages: int) -> ExtractedDocument:
    damaged = ExtractionError(
        "malformed", "This PDF is damaged or not a valid PDF, so its text could not be read."
    )
    try:
        reader = PdfReader(BytesIO(data))
        if reader.is_encrypted:
            # Many PDFs are encrypted only to restrict printing or copying and open with an
            # empty password. Those are readable; real passwords are not asked for.
            try:
                result = reader.decrypt("")
            except DependencyError as exc:
                raise ExtractionError(
                    "encrypted", "This PDF uses an encryption method DocuMind cannot open."
                ) from exc
            if result == PasswordType.NOT_DECRYPTED:
                raise ExtractionError(
                    "encrypted",
                    "This PDF is password-protected. Remove the password and upload it again.",
                )
        page_count = len(reader.pages)
    except ExtractionError:
        raise
    except Exception as exc:
        raise damaged from exc

    if page_count == 0:
        raise ExtractionError("malformed", "This PDF has no pages.")
    if page_count > max_pages:
        raise ExtractionError(
            "too_large", f"This PDF has {page_count:,} pages; the limit is {max_pages:,}."
        )

    pages: list[ExtractedPage] = []
    unreadable_pages = 0
    for number in range(1, page_count + 1):
        try:
            raw = reader.pages[number - 1].extract_text() or ""
        except Exception:
            # One broken page should not lose the rest of the document. It is counted as a page
            # without text, which the user sees.
            unreadable_pages += 1
            raw = ""
        pages.append(ExtractedPage(number=number, text=normalize_text(raw, join_hyphenated=True)))

    if unreadable_pages == page_count:
        raise damaged
    total = sum(_non_whitespace(page.text) for page in pages)
    if total < MIN_CHARS_PER_PAGE * page_count:
        raise ExtractionError(
            "no_extractable_text",
            "This PDF appears to contain scanned images rather than text. DocuMind cannot read "
            "text from images (OCR is not supported).",
        )
    empty = sum(1 for page in pages if _non_whitespace(page.text) == 0)
    return ExtractedDocument(pages=pages, page_count=page_count, empty_page_count=empty)
