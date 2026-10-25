import pytest

from documind.ingestion.extraction import ExtractedDocument, ExtractionError, extract_bytes
from tests.pdf_factory import make_encrypted_pdf, make_pdf, paragraph


def extract(data: bytes, file_type: str = "pdf", **limits: int) -> ExtractedDocument:
    return extract_bytes(
        data,
        file_type,
        max_pages=limits.get("max_pages", 500),
        max_chars=limits.get("max_chars", 2_000_000),
    )


def extract_error(data: bytes, file_type: str = "pdf", **limits: int) -> ExtractionError:
    with pytest.raises(ExtractionError) as caught:
        extract(data, file_type, **limits)
    return caught.value


def test_pdf_text_is_extracted_per_page() -> None:
    data = make_pdf([paragraph("pricing"), paragraph("staffing")])

    document = extract(data)

    assert document.page_count == 2
    assert document.empty_page_count == 0
    assert [p.number for p in document.pages] == [1, 2]
    assert "pricing" in document.pages[0].text
    assert "staffing" in document.pages[1].text
    assert "staffing" not in document.pages[0].text


def test_pdf_pages_without_text_are_counted() -> None:
    data = make_pdf([paragraph("budget"), None, paragraph("audit")])

    document = extract(data)

    assert document.page_count == 3
    assert document.empty_page_count == 1
    assert document.pages[1].text == ""


def test_image_only_pdf_is_reported_as_scanned() -> None:
    error = extract_error(make_pdf([None, None, None]))

    assert error.code == "no_extractable_text"
    assert "scanned" in error.message
    assert "OCR" in error.message


def test_pdf_with_only_a_few_characters_per_page_is_reported_as_scanned() -> None:
    # Scans often carry tiny text layers such as page numbers.
    error = extract_error(make_pdf(["Page 1", "Page 2", "Page 3", "Page 4"]))

    assert error.code == "no_extractable_text"


def test_password_protected_pdf_is_rejected() -> None:
    error = extract_error(make_encrypted_pdf([paragraph("secrets")], user_password="letmein"))

    assert error.code == "encrypted"
    assert "password" in error.message


def test_pdf_encrypted_with_empty_password_is_readable() -> None:
    data = make_encrypted_pdf([paragraph("permissions")], user_password="")

    document = extract(data)

    assert "permissions" in document.pages[0].text


@pytest.mark.parametrize(
    "data",
    [
        b"%PDF-1.4\nthis is not really a pdf at all\n%%EOF",
        make_pdf([paragraph("truncated")])[:300],
        b"%PDF-" + bytes(range(256)) * 40,
    ],
    ids=["garbage", "truncated", "binary-noise"],
)
def test_damaged_pdf_is_reported_as_malformed(data: bytes) -> None:
    error = extract_error(data)

    assert error.code == "malformed"
    assert "damaged" in error.message


def test_pdf_over_the_page_limit_is_rejected() -> None:
    error = extract_error(make_pdf([paragraph("x")] * 4), max_pages=3)

    assert error.code == "too_large"
    assert "4 pages" in error.message


def test_text_over_the_character_limit_is_rejected_not_truncated() -> None:
    error = extract_error(("word " * 5000).encode(), "txt", max_chars=10_000)

    assert error.code == "too_large"


def test_text_file_is_extracted_as_a_single_unnumbered_page() -> None:
    document = extract(b"Line one\r\nLine two", "txt")

    assert document.page_count is None
    assert document.empty_page_count is None
    assert [(p.number, p.text) for p in document.pages] == [(None, "Line one\nLine two")]


def test_whitespace_only_text_file_has_no_extractable_text() -> None:
    error = extract_error(b" \n\t\n  ", "txt")

    assert error.code == "no_extractable_text"


def test_undecodable_text_file_is_reported() -> None:
    error = extract_error("café".encode("latin-1"), "txt")

    assert error.code == "unreadable_text"
