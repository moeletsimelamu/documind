"""Builds small, real PDF files for tests, so no personal documents are needed."""

from collections.abc import Sequence
from io import BytesIO

from pypdf import PdfWriter


def _escape(text: str) -> bytes:
    raw = text.encode("cp1252")
    return raw.replace(b"\\", b"\\\\").replace(b"(", b"\\(").replace(b")", b"\\)")


def _content_stream(text: str | None) -> bytes:
    if text is None:
        # An "image-only" page: draws a filled rectangle and contains no text, like a scan.
        return b"0.5 g 72 300 400 400 re f"
    lines = [b"BT /F1 11 Tf 14 TL 72 760 Td"]
    lines += [b"(" + _escape(line) + b") Tj T*" for line in text.split("\n")]
    lines.append(b"ET")
    return b"\n".join(lines)


def make_pdf(pages: Sequence[str | None]) -> bytes:
    """A PDF with one page per item: text (lines separated by \\n), or None for no text."""
    objects: list[bytes] = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"",  # page tree, filled in below
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding >>",
    ]
    page_refs: list[str] = []
    for text in pages:
        stream = _content_stream(text)
        content_number = len(objects) + 2
        objects.append(
            f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
            f"/Resources << /Font << /F1 3 0 R >> >> /Contents {content_number} 0 R >>".encode()
        )
        page_refs.append(f"{len(objects)} 0 R")
        objects.append(f"<< /Length {len(stream)} >>\nstream\n".encode() + stream + b"\nendstream")
    objects[1] = f"<< /Type /Pages /Kids [{' '.join(page_refs)}] /Count {len(pages)} >>".encode()

    output = BytesIO()
    output.write(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")
    offsets = []
    for number, body in enumerate(objects, start=1):
        offsets.append(output.tell())
        output.write(f"{number} 0 obj\n".encode() + body + b"\nendobj\n")
    xref_at = output.tell()
    output.write(f"xref\n0 {len(objects) + 1}\n0000000000 65535 f \n".encode())
    for offset in offsets:
        output.write(f"{offset:010d} 00000 n \n".encode())
    output.write(
        f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\n"
        f"startxref\n{xref_at}\n%%EOF\n".encode()
    )
    return output.getvalue()


def make_encrypted_pdf(pages: Sequence[str | None], *, user_password: str) -> bytes:
    writer = PdfWriter(clone_from=BytesIO(make_pdf(pages)))
    writer.encrypt(user_password=user_password, owner_password="owner-secret", algorithm="AES-256")
    output = BytesIO()
    writer.write(output)
    return output.getvalue()


def paragraph(topic: str, sentences: int = 6) -> str:
    """Readable filler text about ``topic``, one sentence per line like a PDF text layer."""
    return "\n".join(
        f"Sentence {n} of the section explains how {topic} affects the quarterly results."
        for n in range(1, sentences + 1)
    )
