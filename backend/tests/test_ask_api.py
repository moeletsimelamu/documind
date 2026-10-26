from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from documind.answering.provider import ProviderTimeoutError
from tests.fakes import FakeModel
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


# --- With a language model ---------------------------------------------------------------------


def with_model(client: TestClient, model: FakeModel) -> None:
    app = client.app
    assert isinstance(app, FastAPI)
    app.state.language_model = model


def test_generated_answer_carries_its_citations_and_model(
    client: TestClient, notes: dict[str, Any]
) -> None:
    with_model(
        client,
        FakeModel({"sufficient": True, "answer": "R4.5 million [S1][S4].", "cited": ["S1"]}),
    )

    body = ask(client, question="What budget did the board approve?").json()

    assert body["mode"] == "generated"
    assert body["answer"] == "R4.5 million [S1]."
    assert body["cited"] == ["S1"]
    assert body["model"] == "fake-model"
    assert body["generation_error"] is None
    assert body["passages"][0]["document_id"] == notes["id"]


def test_provider_failure_is_reported_alongside_the_passages(
    client: TestClient, notes: dict[str, Any]
) -> None:
    with_model(
        client, FakeModel(error=ProviderTimeoutError("The AI provider did not respond in time."))
    )

    body = ask(client, question="What budget did the board approve?").json()

    assert body["mode"] == "retrieval_only"
    assert body["answer"] is None
    assert body["generation_error"] == {
        "code": "provider_timeout",
        "message": "The AI provider did not respond in time.",
    }
    assert body["passages"]


def test_app_builds_no_model_client_when_ai_is_off(client: TestClient) -> None:
    app = client.app
    assert isinstance(app, FastAPI)
    assert app.state.language_model is None
