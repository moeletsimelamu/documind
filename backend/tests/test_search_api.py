from typing import Any

import pytest
from fastapi.testclient import TestClient

from tests.pdf_factory import make_pdf
from tests.test_documents_api import uploaded

HANDBOOK = """Staff handbook

Leave
Full-time staff receive 21 working days of paid vacation per year.
Unused days can be carried over until 31 March.

Expenses
Claims must be submitted within 30 days with receipts attached.
"""

REPORT_PAGES = [
    "Q3 operations report\nRevenue rose 8 percent compared with Q2.",
    "Logistics\nSupplier delays at the Durban port slowed deliveries for six weeks.\n"
    "A second supplier was contracted in August.",
    "Outlook\nDeliveries are expected to normalise by November.",
]


@pytest.fixture
def library(client: TestClient) -> dict[str, dict[str, Any]]:
    return {
        "handbook": uploaded(client, "handbook.txt", HANDBOOK.encode()),
        "report": uploaded(client, "q3-report.pdf", make_pdf(REPORT_PAGES)),
    }


def search(client: TestClient, **params: Any) -> Any:
    return client.get("/api/search", params=params)


def test_search_returns_located_highlighted_passages(
    client: TestClient, library: dict[str, dict[str, Any]]
) -> None:
    body = search(client, q="Which supplier caused delivery delays?").json()

    assert body["searched_for"] == ["supplier", "caused", "delivery", "delays"]
    assert body["total_documents"] == 1
    top = body["results"][0]
    assert top["document_id"] == library["report"]["id"]
    assert top["document_name"] == "q3-report.pdf"
    assert top["page"] == 2
    assert top["line_start"] is None
    marked = [top["excerpt"][s:e] for s, e in top["highlights"]]
    assert {"Supplier", "delays", "deliveries"} <= set(marked)


def test_text_file_results_carry_line_ranges(
    client: TestClient, library: dict[str, dict[str, Any]]
) -> None:
    top = search(client, q="vacation").json()["results"][0]

    assert top["document_id"] == library["handbook"]["id"]
    assert top["page"] is None
    assert top["line_start"] <= 4 <= top["line_end"]


def test_no_results(client: TestClient, library: dict[str, dict[str, Any]]) -> None:
    body = search(client, q="zebra").json()

    assert body["results"] == []
    assert body["total_passages"] == 0


def test_search_can_be_scoped_to_a_document(
    client: TestClient, library: dict[str, dict[str, Any]]
) -> None:
    everywhere = search(client, q="days").json()
    scoped = search(client, q="days", document_id=library["report"]["id"]).json()

    assert everywhere["total_documents"] == 1  # "days" is only in the handbook
    assert scoped["total_passages"] == 0


@pytest.mark.parametrize(
    ("params", "code"),
    [
        ({"q": "?!"}, "empty_query"),
        ({"q": "budget " * 60}, "query_too_long"),
        ({}, "invalid_request"),
        ({"q": "budget", "limit": 0}, "invalid_request"),
        ({"q": "budget", "limit": 51}, "invalid_request"),
        ({"q": "budget", "document_id": "not-a-uuid"}, "invalid_request"),
    ],
)
def test_invalid_searches_are_rejected(
    client: TestClient, params: dict[str, Any], code: str
) -> None:
    response = search(client, **params)

    assert response.status_code == 422
    assert response.json()["error"]["code"] == code


def test_deleted_documents_disappear_from_results(
    client: TestClient, library: dict[str, dict[str, Any]]
) -> None:
    assert search(client, q="supplier").json()["total_passages"] > 0

    client.delete(f"/api/documents/{library['report']['id']}")

    assert search(client, q="supplier").json()["total_passages"] == 0


def test_document_text_is_returned_as_plain_text(client: TestClient) -> None:
    uploaded(client, "page.txt", b"Example markup: <script>alert('x')</script> budget <b>bold</b>")

    hit = search(client, q="budget").json()["results"][0]

    assert "<script>alert('x')</script>" in hit["excerpt"]
    assert "<mark>" not in hit["excerpt"]


def test_chunk_lookup_opens_a_search_result(
    client: TestClient, library: dict[str, dict[str, Any]]
) -> None:
    hit = search(client, q="Durban").json()["results"][0]

    chunk = client.get(f"/api/chunks/{hit['chunk_id']}").json()

    assert chunk["document_id"] == library["report"]["id"]
    assert chunk["document_name"] == "q3-report.pdf"
    assert chunk["page"] == 2
    assert "Durban port" in chunk["text"]
    assert chunk["ordinal"] == hit["ordinal"]


def test_missing_chunk_is_not_found(client: TestClient) -> None:
    response = client.get("/api/chunks/999999")

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "not_found"
