from typing import Any

import pytest
from fastapi.testclient import TestClient

from tests.test_documents_api import uploaded

NOTES = b"Board meeting\n\nThe board approved a budget of R4.5 million for Project Falcon.\n"


@pytest.fixture
def notes(client: TestClient) -> dict[str, Any]:
    return uploaded(client, "board-notes.txt", NOTES)


def ask(client: TestClient, **body: Any) -> Any:
    return client.post("/api/ask", json=body)


def test_without_ai_the_response_is_the_retrieved_evidence(
    client: TestClient, notes: dict[str, Any]
) -> None:
    body = ask(client, question="What budget did the board approve?").json()

    assert body["mode"] == "retrieval_only"
    assert body["answer"] is None
    assert body["searched_for"] == ["budget", "board", "approve"]
    assert body["passages"][0]["document_id"] == notes["id"]
    assert "R4.5 million" in body["passages"][0]["excerpt"]


def test_no_matching_passages_is_insufficient_evidence(
    client: TestClient, notes: dict[str, Any]
) -> None:
    body = ask(client, question="Who won the football match?").json()

    assert body["mode"] == "insufficient_evidence"
    assert body["answer"] is None
    assert body["passages"] == []


def test_empty_library_is_insufficient_evidence(client: TestClient) -> None:
    assert ask(client, question="What is the budget?").json()["mode"] == "insufficient_evidence"


def test_question_can_be_scoped_to_documents(client: TestClient, notes: dict[str, Any]) -> None:
    other = uploaded(client, "other.txt", b"Nothing about money here.")

    body = ask(client, question="budget", document_ids=[other["id"]]).json()

    assert body["mode"] == "insufficient_evidence"


@pytest.mark.parametrize(
    ("body", "code"),
    [
        ({"question": "?!"}, "empty_query"),
        ({"question": "   "}, "empty_query"),
        ({"question": "why " * 300}, "question_too_long"),
        ({"question": ""}, "invalid_request"),
        ({}, "invalid_request"),
        ({"question": "budget", "document_ids": ["nope"]}, "invalid_request"),
    ],
)
def test_invalid_questions_are_rejected(
    client: TestClient, body: dict[str, Any], code: str
) -> None:
    response = client.post("/api/ask", json=body)

    assert response.status_code == 422
    assert response.json()["error"]["code"] == code
