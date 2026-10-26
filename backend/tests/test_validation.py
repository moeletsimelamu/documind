import codecs

import pytest

from documind.ingestion.validation import (
    TextDecodingError,
    UnsupportedFileError,
    check_content,
    decode_text,
    file_type_from_name,
    sanitize_display_name,
)


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("report.pdf", "report.pdf"),
        ("../../etc/passwd.txt", "passwd.txt"),
        ("..\\..\\Windows\\system.ini.txt", "system.ini.txt"),
        ("C:\\Users\\me\\Documents\\notes.txt", "notes.txt"),
        ("quarterly\x00report.pdf", "quarterlyreport.pdf"),
        ("report\r\nSet-Cookie: x.txt", "reportSet-Cookie: x.txt"),  # no line breaks in headers
        ("invoice\u202efdp.exe", "invoicefdp.exe"),  # right-to-left override removed
        ("  spaced    out   name.txt  ", "spaced out name.txt"),
        ("Cafe\u0301 menu.txt", "Café menu.txt"),  # normalised to NFC
        ("", "untitled"),
        (None, "untitled"),
        ("/", "untitled"),
    ],
)
def test_sanitize_display_name(raw: str | None, expected: str) -> None:
    assert sanitize_display_name(raw) == expected


def test_long_names_are_shortened_but_keep_their_extension() -> None:
    name = sanitize_display_name("a" * 500 + ".pdf")

    assert len(name) == 200
    assert name.endswith(".pdf")


@pytest.mark.parametrize(
    ("name", "expected"), [("a.pdf", "pdf"), ("B.PDF", "pdf"), ("c.Txt", "txt")]
)
def test_supported_extensions(name: str, expected: str) -> None:
    assert file_type_from_name(name) == expected


@pytest.mark.parametrize("name", ["report.docx", "virus.exe", "archive.pdf.zip", "README", ".pdf"])
def test_unsupported_extensions_are_rejected(name: str) -> None:
    with pytest.raises(UnsupportedFileError) as caught:
        file_type_from_name(name)

    assert caught.value.status_code == 415
    assert "Upload PDF and TXT files" in caught.value.message


def test_pdf_content_must_start_with_pdf_signature() -> None:
    check_content("pdf", b"%PDF-1.7\n...")
    check_content("pdf", b"\xef\xbb\xbf junk before header %PDF-1.4")

    with pytest.raises(UnsupportedFileError, match="not a PDF"):
        check_content("pdf", b"PK\x03\x04 a zip file renamed to .pdf")


def test_decode_text_accepts_utf8_with_and_without_bom() -> None:
    assert decode_text("naïve café".encode()) == "naïve café"
    assert decode_text(codecs.BOM_UTF8 + b"hello") == "hello"


def test_decode_text_accepts_utf16_with_bom() -> None:
    assert decode_text("hello wörld".encode("utf-16")) == "hello wörld"


def test_decode_text_rejects_binary_data() -> None:
    with pytest.raises(TextDecodingError, match="binary data"):
        decode_text(b"MZ\x90\x00\x03\x00 executable")


def test_decode_text_rejects_other_encodings() -> None:
    with pytest.raises(TextDecodingError, match="not UTF-8"):
        decode_text("naïve café".encode("latin-1"))
