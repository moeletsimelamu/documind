"""Document upload, processing, listing, download and deletion through the HTTP API.

The test client runs background tasks before returning, so a document is already processed
(ready or failed) when the upload call returns, while the upload response itself still shows the
``processing`` state the browser sees.
"""

import hashlib
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from documind.api import documents
from documind.config import Settings
from documind.ingestion import pipeline
from documind.ingestion.extraction import extract_bytes
from documind.main import create_app
from documind.models import Chunk, Document, DocumentStatus
from tests.conftest import make_settings
from tests.pdf_factory import make_encrypted_pdf, make_pdf, paragraph

TXT_BODY = (
    "Project Falcon kickoff\n\nThe budget for Falcon is 1.2 million rand.\nRisks: supplier delays."
)


def upload(client: TestClient, name: str, data: bytes) -> Any:
    return client.post("/api/documents", files={"file": (name, data, "application/octet-stream")})


def uploaded(client: TestClient, name: str, data: bytes) -> dict[str, Any]:
    response = upload(client, name, data)
    assert response.status_code == 202, response.text
    document: dict[str, Any] = client.get(f"/api/documents/{response.json()['id']}").json()
    return document


def session_for(app: FastAPI) -> Session:
    session: Session = app.state.session_factory()
    return session


def fts_matches(app: FastAPI, term: str) -> int:
    with session_for(app) as session:
        count: int = session.execute(
            text("SELECT count(*) FROM chunks_fts WHERE chunks_fts MATCH :t"), {"t": term}
        ).scalar_one()
        return count


def stored_files(settings: Settings) -> list[str]:
    return sorted(p.name for p in settings.uploads_dir.iterdir())


# --- Successful processing -------------------------------------------------------------------


def test_text_upload_is_accepted_then_indexed(client: TestClient, app: FastAPI) -> None:
    response = upload(client, "falcon-notes.txt", TXT_BODY.encode())

    assert response.status_code == 202
    body = response.json()
    assert body["status"] == "processing"
    assert body["name"] == "falcon-notes.txt"
    assert body["file_type"] == "txt"
    assert body["size_bytes"] == len(TXT_BODY.encode())
    assert "stored_name" not in body
    assert "sha256" not in body

    document = client.get(f"/api/documents/{body['id']}").json()
    assert document["status"] == "ready"
    assert document["chunk_count"] == 1
    assert document["page_count"] is None
    assert document["failure_code"] is None
    assert document["processed_at"] is not None

    chunks = client.get(f"/api/documents/{body['id']}/chunks").json()
    assert chunks["total"] == 1
    assert chunks["items"][0]["line_start"] == 1
    assert chunks["items"][0]["line_end"] == 4
    assert chunks["items"][0]["page"] is None
    assert fts_matches(app, "supplier") == 1


def test_pdf_chunks_keep_their_page_numbers(client: TestClient, app: FastAPI) -> None:
    data = make_pdf([paragraph("pricing"), paragraph("staffing"), paragraph("logistics")])

    document = uploaded(client, "quarterly.pdf", data)

    assert document["status"] == "ready"
    assert document["page_count"] == 3
    assert document["empty_page_count"] == 0
    items = client.get(f"/api/documents/{document['id']}/chunks").json()["items"]
    pages = {item["page"]: item["text"] for item in items}
    assert set(pages) == {1, 2, 3}
    assert "staffing" in pages[2]
    assert "staffing" not in pages[1] + pages[3]
    assert all(item["line_start"] is None for item in items)


def test_pdf_with_some_image_only_pages_is_indexed_and_reports_them(client: TestClient) -> None:
    document = uploaded(client, "mixed.pdf", make_pdf([paragraph("intro"), None, paragraph("end")]))

    assert document["status"] == "ready"
    assert document["empty_page_count"] == 1


def test_large_text_document_is_fully_indexed(client: TestClient, app: FastAPI) -> None:
    lines = [f"Record {n}: shipment {n} arrived at warehouse {n % 7}." for n in range(5000)]
    body = "\n".join(lines)

    document = uploaded(client, "log.txt", body.encode())

    assert document["status"] == "ready"
    page = client.get(f"/api/documents/{document['id']}/chunks", params={"limit": 200}).json()
    assert page["total"] == document["chunk_count"] > 100
    with session_for(app) as session:
        texts = session.scalars(select(Chunk.text).order_by(Chunk.ordinal)).all()
    assert "".join("".join(texts).split()) == "".join(body.split())


# --- Rejected uploads ------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("name", "data", "status", "code", "message"),
    [
        ("report.docx", b"PK\x03\x04", 415, "unsupported_file_type", "not supported"),
        ("invoice.pdf", b"PK\x03\x04 zip pretending", 415, "unsupported_file_type", "not a PDF"),
        ("binary.txt", b"MZ\x90\x00\x03", 415, "unsupported_file_type", "binary data"),
        ("latin1.txt", "café".encode("latin-1"), 415, "unsupported_file_type", "UTF-8"),
        ("empty.pdf", b"", 422, "empty_file", "empty"),
    ],
)
def test_invalid_uploads_are_rejected_and_nothing_is_stored(
    client: TestClient,
    settings: Settings,
    name: str,
    data: bytes,
    status: int,
    code: str,
    message: str,
) -> None:
    response = upload(client, name, data)

    assert response.status_code == status
    assert response.json()["error"]["code"] == code
    assert message in response.json()["error"]["message"]
    assert client.get("/api/documents").json() == []
    assert stored_files(settings) == []


def test_upload_without_a_file_is_invalid(client: TestClient) -> None:
    response = client.post("/api/documents", data={"note": "no file here"})

    assert response.status_code == 422
    assert response.json()["error"]["details"][0]["location"] == ["body", "file"]


@pytest.fixture
def small_limit_client(tmp_path: Path) -> Iterator[tuple[TestClient, Settings]]:
    settings = make_settings(tmp_path / "data", max_upload_mb=1)
    with TestClient(create_app(settings)) as client:
        yield client, settings


def test_file_over_the_size_limit_is_rejected(
    small_limit_client: tuple[TestClient, Settings],
) -> None:
    client, settings = small_limit_client

    response = upload(client, "big.txt", b"a" * (1024 * 1024 + 1))

    assert response.status_code == 413
    assert response.json()["error"]["code"] == "file_too_large"
    assert "1 MB" in response.json()["error"]["message"]
    assert stored_files(settings) == []


def test_oversized_body_is_refused_from_content_length_alone(
    small_limit_client: tuple[TestClient, Settings],
) -> None:
    client, _ = small_limit_client

    response = client.post(
        "/api/documents",
        content=b"x" * 10,
        headers={"Content-Type": "multipart/form-data; boundary=b", "Content-Length": "5000000"},
    )

    assert response.status_code == 413
    assert response.json()["error"]["code"] == "file_too_large"
    assert response.headers["X-Request-ID"]


def test_oversized_body_without_content_length_is_cut_off(
    small_limit_client: tuple[TestClient, Settings], monkeypatch: pytest.MonkeyPatch
) -> None:
    client, settings = small_limit_client
    handler_calls: list[object] = []
    monkeypatch.setattr(documents, "accept_upload", lambda **kw: handler_calls.append(kw))

    def body() -> Iterator[bytes]:
        yield b'--b\r\nContent-Disposition: form-data; name="file"; filename="big.txt"\r\n\r\n'
        for _ in range(40):
            yield b"a" * 64 * 1024  # 2.5 MB in total, streamed without a Content-Length
        yield b"\r\n--b--\r\n"

    response = client.post(
        "/api/documents",
        content=body(),
        headers={"Content-Type": "multipart/form-data; boundary=b"},
    )

    assert response.status_code == 413
    assert response.json()["error"]["code"] == "file_too_large"
    assert stored_files(settings) == []
    # Stopped while receiving, before the multipart body was parsed and handed to the endpoint.
    assert handler_calls == []


def test_duplicate_file_is_rejected_with_a_link_to_the_original(client: TestClient) -> None:
    first = upload(client, "contract.txt", b"The notice period is 30 days.").json()

    response = upload(client, "contract-copy.txt", b"The notice period is 30 days.")

    assert response.status_code == 409
    error = response.json()["error"]
    assert error["code"] == "duplicate_document"
    assert error["details"] == {"document_id": first["id"], "status": "ready"}
    assert "contract.txt" in error["message"]
    assert len(client.get("/api/documents").json()) == 1


def test_files_with_the_same_name_but_different_content_are_both_kept(client: TestClient) -> None:
    upload(client, "notes.txt", b"version one")
    upload(client, "notes.txt", b"version two")

    assert [d["name"] for d in client.get("/api/documents").json()] == ["notes.txt", "notes.txt"]


def test_path_in_file_name_never_reaches_the_file_system(
    client: TestClient, settings: Settings, tmp_path: Path
) -> None:
    document = uploaded(client, "../../../outside.txt", b"traversal attempt")

    assert document["name"] == "outside.txt"
    assert stored_files(settings) == [f"{document['id']}.txt"]
    assert not (tmp_path / "outside.txt").exists()
    assert not (settings.data_dir / "outside.txt").exists()


# --- Processing failures ---------------------------------------------------------------------


@pytest.mark.parametrize(
    ("data", "code", "message"),
    [
        (make_pdf([None, None]), "no_extractable_text", "scanned"),
        (b"%PDF-1.4\nnot really a pdf\n%%EOF", "malformed", "damaged"),
        (make_encrypted_pdf([paragraph("x")], user_password="pw"), "encrypted", "password"),
    ],
    ids=["scanned", "malformed", "encrypted"],
)
def test_unreadable_pdfs_are_recorded_as_failed_with_a_reason(
    client: TestClient, app: FastAPI, data: bytes, code: str, message: str
) -> None:
    document = uploaded(client, "problem.pdf", data)

    assert document["status"] == "failed"
    assert document["failure_code"] == code
    assert message in document["failure_message"]
    assert document["chunk_count"] == 0
    assert client.get(f"/api/documents/{document['id']}/chunks").json()["total"] == 0


def test_pdf_over_the_page_limit_fails(tmp_path: Path) -> None:
    settings = make_settings(tmp_path / "data", max_pdf_pages=2)
    with TestClient(create_app(settings)) as client:
        document = uploaded(client, "long.pdf", make_pdf([paragraph("x")] * 3))

    assert document["status"] == "failed"
    assert document["failure_code"] == "too_large"


def test_processing_that_exceeds_the_time_limit_fails(tmp_path: Path) -> None:
    # Far shorter than it takes to start the extraction process.
    settings = make_settings(tmp_path / "data", extraction_timeout_seconds=0.01)
    with TestClient(create_app(settings)) as client:
        document = uploaded(client, "slow.txt", b"some text")

    assert document["status"] == "failed"
    assert document["failure_code"] == "timeout"


def test_unexpected_processing_error_is_recorded_and_logged(
    client: TestClient, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    def broken(_: object) -> list[object]:
        raise RuntimeError("bug")

    monkeypatch.setattr(pipeline, "build_chunks", broken)

    document = uploaded(client, "notes.txt", b"hello")

    assert document["status"] == "failed"
    assert document["failure_code"] == "processing_error"
    assert "unexpected error" in document["failure_message"]
    assert any(r.exc_info for r in caplog.records if r.name == "documind.ingestion.pipeline")


# --- Listing, reading, downloading -----------------------------------------------------------


def test_library_is_listed_newest_first_and_can_be_filtered(client: TestClient) -> None:
    upload(client, "Alpha report.txt", b"alpha")
    upload(client, "beta_notes.txt", b"beta")
    upload(client, "scan.pdf", make_pdf([None]))

    names = [d["name"] for d in client.get("/api/documents").json()]
    assert names == ["scan.pdf", "beta_notes.txt", "Alpha report.txt"]

    def listed(**params: str) -> list[str]:
        return [d["name"] for d in client.get("/api/documents", params=params).json()]

    assert listed(q="REPORT") == ["Alpha report.txt"]
    assert listed(q="_") == ["beta_notes.txt"]  # LIKE wildcards are matched literally
    assert listed(q="%") == []
    assert listed(status="failed") == ["scan.pdf"]
    assert listed(status="ready", q="a") == ["beta_notes.txt", "Alpha report.txt"]


def test_invalid_status_filter_is_rejected(client: TestClient) -> None:
    assert client.get("/api/documents", params={"status": "done"}).status_code == 422


def test_empty_library(client: TestClient) -> None:
    assert client.get("/api/documents").json() == []


def test_unknown_document_is_not_found(client: TestClient) -> None:
    missing = "00000000-0000-4000-8000-000000000000"

    for path in ("", "/chunks", "/file"):
        response = client.get(f"/api/documents/{missing}{path}")
        assert response.status_code == 404
        assert response.json()["error"]["code"] == "not_found"
    assert client.delete(f"/api/documents/{missing}").status_code == 404


def test_malformed_document_id_is_rejected(client: TestClient) -> None:
    response = client.get("/api/documents/..%2F..%2Fdocumind.db")

    assert response.status_code in (404, 422)
    assert client.get("/api/documents/not-a-uuid").status_code == 422


def test_chunks_are_paginated_in_document_order(client: TestClient) -> None:
    body = "\n\n".join(f"Paragraph {n}. " + "filler words " * 70 for n in range(10))
    document = uploaded(client, "long.txt", body.encode())

    first = client.get(f"/api/documents/{document['id']}/chunks", params={"limit": 3}).json()
    rest = client.get(
        f"/api/documents/{document['id']}/chunks", params={"offset": 3, "limit": 200}
    ).json()

    assert first["total"] == rest["total"] == document["chunk_count"]
    ordinals = [c["ordinal"] for c in first["items"] + rest["items"]]
    assert ordinals == list(range(document["chunk_count"]))
    too_many = client.get(f"/api/documents/{document['id']}/chunks", params={"limit": 201})
    assert too_many.status_code == 422


def test_chunks_can_start_at_a_pdf_page(client: TestClient) -> None:
    # Page 3 has no text: asking for it opens at page 4, the next page that has some.
    pages = [
        paragraph("intro"),
        paragraph("pricing"),
        None,
        paragraph("staffing"),
        paragraph("end"),
    ]
    document = uploaded(client, "pages.pdf", make_pdf(pages))
    url = f"/api/documents/{document['id']}/chunks"

    page_two = client.get(url, params={"page": 2, "limit": 1}).json()
    empty_page = client.get(url, params={"page": 3, "limit": 1}).json()
    past_end = client.get(url, params={"page": 99, "limit": 5}).json()

    assert page_two["items"][0]["page"] == 2
    assert page_two["offset"] == page_two["items"][0]["ordinal"]
    assert empty_page["items"][0]["page"] == 4
    assert [item["page"] for item in past_end["items"]] == [5]  # the last passage
    assert client.get(url, params={"page": 0}).status_code == 422


def test_find_in_document_lists_matches_in_reading_order_with_highlights(
    client: TestClient,
) -> None:
    pages = [paragraph("pricing"), paragraph("supplier delays"), paragraph("supplier costs")]
    document = uploaded(client, "find.pdf", make_pdf(pages))
    uploaded(client, "other.txt", b"Supplier delays elsewhere must not be listed.")
    url = f"/api/documents/{document['id']}/matches"

    result = client.get(url, params={"q": "the supplier"}).json()
    chunks = {
        c["id"]: c["text"]
        for c in client.get(f"/api/documents/{document['id']}/chunks").json()["items"]
    }

    assert result["searched_for"] == ["supplier"]
    assert [m["page"] for m in result["matches"]] == [2, 3]
    assert result["total"] == 2 and result["truncated"] is False
    for match in result["matches"]:
        text_ = chunks[match["chunk_id"]]
        assert {text_[s:e].lower() for s, e in match["highlights"]} == {"supplier"}


def test_find_in_document_wants_all_words_and_falls_back_to_any(client: TestClient) -> None:
    pages = [paragraph("pricing"), paragraph("supplier delays"), paragraph("supplier costs")]
    document = uploaded(client, "words.pdf", make_pdf(pages))
    url = f"/api/documents/{document['id']}/matches"

    both = client.get(url, params={"q": "supplier costs"}).json()
    neither = client.get(url, params={"q": "supplier unicorn"}).json()

    assert [m["page"] for m in both["matches"]] == [3]  # not every passage with "supplier"
    assert both["all_words"] is True
    assert [m["page"] for m in neither["matches"]] == [2, 3]  # no page has both: any one counts
    assert neither["all_words"] is False


def test_find_in_document_rejects_empty_and_too_long_queries(client: TestClient) -> None:
    document = uploaded(client, "notes.txt", TXT_BODY.encode())
    url = f"/api/documents/{document['id']}/matches"

    assert client.get(url, params={"q": "  "}).json()["error"]["code"] == "empty_query"
    assert client.get(url, params={"q": "x" * 301}).json()["error"]["code"] == "query_too_long"
    assert client.get(url, params={"q": 'NEAR(budget) "falcon'}).status_code == 200  # inert
    assert (
        client.get(
            "/api/documents/00000000-0000-0000-0000-000000000000/matches", params={"q": "x"}
        ).status_code
        == 404
    )


def test_original_file_downloads_as_an_attachment(client: TestClient) -> None:
    data = make_pdf([paragraph("download")])
    document = uploaded(client, "Résumé 2026.pdf", data)

    response = client.get(f"/api/documents/{document['id']}/file")

    assert response.status_code == 200
    assert response.content == data
    assert response.headers["content-type"] == "application/pdf"
    assert response.headers["content-disposition"].startswith("attachment;")
    assert "R%C3%A9sum%C3%A9%202026.pdf" in response.headers["content-disposition"]
    assert response.headers["x-content-type-options"] == "nosniff"


# --- Deletion --------------------------------------------------------------------------------


def test_delete_removes_record_chunks_index_entries_and_file(
    client: TestClient, app: FastAPI, settings: Settings
) -> None:
    keep = uploaded(client, "keep.txt", b"The warehouse audit is in May.")
    remove = uploaded(client, "remove.pdf", make_pdf([paragraph("warehouse")] * 2))
    assert fts_matches(app, "warehouse") == 3

    response = client.delete(f"/api/documents/{remove['id']}")

    assert response.status_code == 204
    assert client.get(f"/api/documents/{remove['id']}").status_code == 404
    assert [d["id"] for d in client.get("/api/documents").json()] == [keep["id"]]
    assert stored_files(settings) == [f"{keep['id']}.txt"]
    with session_for(app) as session:
        remaining = session.scalars(select(Chunk.document_id).distinct()).all()
        # FTS5's own consistency check between the index and the chunks table.
        session.execute(text("INSERT INTO chunks_fts(chunks_fts) VALUES ('integrity-check')"))
    assert remaining == [keep["id"]]
    assert fts_matches(app, "warehouse") == 1
    assert client.delete(f"/api/documents/{remove['id']}").status_code == 404


def test_failed_document_can_be_deleted_and_uploaded_again(client: TestClient) -> None:
    data = b"%PDF-1.4\nbroken\n%%EOF"
    failed = uploaded(client, "broken.pdf", data)
    assert upload(client, "broken.pdf", data).status_code == 409

    client.delete(f"/api/documents/{failed['id']}")

    assert upload(client, "broken.pdf", data).status_code == 202


def test_document_deleted_during_processing_is_discarded(
    client: TestClient, app: FastAPI, monkeypatch: pytest.MonkeyPatch
) -> None:
    processor = app.state.processor
    queued: list[str] = []
    monkeypatch.setattr(processor, "process", queued.append)
    document = upload(client, "notes.txt", b"short lived").json()
    client.delete(f"/api/documents/{document['id']}")
    monkeypatch.undo()

    processor.process(queued[0])  # the background job runs after the delete

    with session_for(app) as session:
        assert session.scalar(select(func.count()).select_from(Chunk)) == 0
        assert session.get(Document, document["id"]) is None


def test_chunks_are_not_written_for_a_document_deleted_mid_write(
    client: TestClient, app: FastAPI
) -> None:
    document = uploaded(client, "notes.txt", b"some content to index")
    extracted = extract_bytes(b"new content", "txt", max_pages=10, max_chars=1000)
    client.delete(f"/api/documents/{document['id']}")

    stored = app.state.processor._store(document["id"], extracted, pipeline.build_chunks(extracted))

    assert stored is False
    with session_for(app) as session:
        assert session.scalar(select(func.count()).select_from(Chunk)) == 0


# --- Restart recovery ------------------------------------------------------------------------


def test_restart_fails_interrupted_documents_and_removes_orphaned_files(tmp_path: Path) -> None:
    settings = make_settings(tmp_path / "data")
    with TestClient(create_app(settings)) as client:
        kept = uploaded(client, "kept.txt", b"kept content")
        app = client.app
        assert isinstance(app, FastAPI)
        with session_for(app) as session:
            session.add(
                Document(
                    id="11111111-1111-4111-8111-111111111111",
                    display_name="half-done.txt",
                    stored_name="11111111-1111-4111-8111-111111111111.txt",
                    file_type="txt",
                    size_bytes=4,
                    sha256=hashlib.sha256(b"half").hexdigest(),
                    status=DocumentStatus.PROCESSING,
                )
            )
            session.commit()
    (settings.uploads_dir / "11111111-1111-4111-8111-111111111111.txt").write_bytes(b"half")
    (settings.uploads_dir / "22222222-2222-4222-8222-222222222222.pdf").write_bytes(b"orphan")
    (settings.uploads_dir / ".upload-abandoned").write_bytes(b"partial upload")
    (settings.uploads_dir / "someone-elses-file.md").write_bytes(b"not ours")

    with TestClient(create_app(settings)) as client:
        interrupted = client.get("/api/documents/11111111-1111-4111-8111-111111111111").json()
        assert client.get(f"/api/documents/{kept['id']}").json()["status"] == "ready"

    assert interrupted["status"] == "failed"
    assert interrupted["failure_code"] == "interrupted"
    assert stored_files(settings) == sorted(
        [
            f"{kept['id']}.txt",
            "11111111-1111-4111-8111-111111111111.txt",
            "someone-elses-file.md",
        ]
    )


def test_running_out_of_memory_while_reading_is_reported_as_too_large(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    def out_of_memory(*_: object, **__: object) -> object:
        raise MemoryError

    monkeypatch.setattr(pipeline, "run_isolated", out_of_memory)

    document = uploaded(client, "bomb.pdf", make_pdf([paragraph("x")]))

    assert document["status"] == "failed"
    assert document["failure_code"] == "too_large"
    assert "1024 MB limit" in document["failure_message"]
