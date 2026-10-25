import pathlib, sys
def sub(path, pairs):
    p = pathlib.Path(path); t = p.read_text(encoding="utf-8")
    for a, b in pairs:
        assert t.count(a) == 1, (path, a[:60]); t = t.replace(a, b)
    p.write_text(t, encoding="utf-8")

sub("src/documind/ingestion/extraction.py", [
 ('''``extract_document`` runs in a separate process (see ``isolation.py``), so everything it takes
and returns is plain picklable data.
"""''', '''``extract_file`` runs in a separate process (see ``isolation.py``). It is given the path of the
stored file rather than its contents, so starting the process never has to transfer a large
payload; everything it returns is plain picklable data.
"""'''),
 ("from io import BytesIO\n", "from io import BytesIO\nfrom pathlib import Path\n"),
 ('''class ExtractionRequest:
    data: bytes
''', '''class ExtractionRequest:
    path: str
'''),
 ('''def extract_document(request: ExtractionRequest) -> ExtractedDocument:
    if request.file_type == "pdf":
        document = _extract_pdf(request.data, request.max_pages)
    elif request.file_type == "txt":
        document = _extract_txt(request.data)
    else:
        raise ExtractionError("unsupported_file_type", "This file type is not supported.")

    if document.char_count > request.max_chars:
        raise ExtractionError(
            "too_large",
            f"The document contains more than {request.max_chars:,} characters of text, "
            "which is the limit.",
        )
    return document
''', '''def extract_file(request: ExtractionRequest) -> ExtractedDocument:
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
'''),
])

sub("src/documind/ingestion/pipeline.py", [
 ('''    ExtractionRequest,
    extract_document,
''', '''    ExtractionRequest,
    extract_file,
'''),
 ('''        try:
            data = self._storage.read_bytes(stored_name)
        except FileNotFoundError:
            self._mark_failed(
                document_id,
                "file_missing",
                "The uploaded file is missing from storage. Delete this document and upload "
                "the file again.",
            )
            return

        request = ExtractionRequest(
            data=data,
''', '''        request = ExtractionRequest(
            path=str(self._storage.path_for(stored_name)),
'''),
 ("            extracted = run_isolated(extract_document, request, timeout)\n",
  "            extracted = run_isolated(extract_file, request, timeout)\n"),
])

p = pathlib.Path("tests/test_extraction.py"); t = p.read_text(encoding="utf-8")
t = t.replace('''from documind.ingestion.extraction import (
    ExtractionError,
    ExtractionRequest,
    extract_document,
)''', '''from documind.ingestion.extraction import ExtractedDocument, ExtractionError, extract_bytes''')
t = t.replace('''def extract(data: bytes, file_type: str = "pdf", **limits: int) -> object:
    request = ExtractionRequest(
        data=data,
        file_type=file_type,
        max_pages=limits.get("max_pages", 500),
        max_chars=limits.get("max_chars", 2_000_000),
    )
    return extract_document(request)''', '''def extract(data: bytes, file_type: str = "pdf", **limits: int) -> ExtractedDocument:
    return extract_bytes(
        data,
        file_type,
        max_pages=limits.get("max_pages", 500),
        max_chars=limits.get("max_chars", 2_000_000),
    )''')
t = t.replace('extract_document(ExtractionRequest(data, "pdf", 500, 2_000_000))', 'extract(data)')
t = t.replace('extract_document(ExtractionRequest(b"Line one\r\nLine two", "txt", 500, 2_000_000))', 'extract(b"Line one\r\nLine two", "txt")')
assert "ExtractionRequest" not in t and "extract_document" not in t, "leftover"
p.write_text(t, encoding="utf-8")

sub("tests/test_documents_api.py", [
 ("from documind.ingestion.extraction import ExtractionRequest, extract_document\n", "from documind.ingestion.extraction import extract_bytes\n"),
 ('''    extracted = extract_document(ExtractionRequest(b"new content", "txt", 10, 1000))''',
  '''    extracted = extract_bytes(b"new content", "txt", max_pages=10, max_chars=1000)'''),
])
print("ok")
