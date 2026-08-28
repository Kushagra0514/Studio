import json
import sys
from pathlib import Path
from types import ModuleType, SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from backend.app import api


@pytest.fixture
def client(monkeypatch, tmp_path):
    monkeypatch.setattr(api.app.state, "ready", True)
    monkeypatch.setattr(
        api.app.state,
        "data_paths",
        SimpleNamespace(history_file=tmp_path / "chat" / "history.json"),
        raising=False,
    )
    test_client = TestClient(api.app)
    yield test_client
    test_client.close()


class RecordingStorage:
    def __init__(self):
        self.added_chunks = []

    def add_chunks(self, chunks):
        self.added_chunks.extend(chunks)


def fake_ingestion_module(**functions):
    module = ModuleType("ingestion")
    for name, function in functions.items():
        setattr(module, name, function)
    return module


def test_health_reports_ready_without_calling_external_services(client):
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}

    api.app.state.ready = False
    response = client.get("/api/health")
    assert response.status_code == 503
    assert response.json() == {"detail": "Service is starting."}


@pytest.mark.parametrize(
    "payload",
    [
        {"question": "   ", "chat_history": []},
        {
            "question": "valid",
            "chat_history": [{"role": "system", "content": "not allowed"}],
        },
        {
            "question": "valid",
            "chat_history": [{"role": "user", "content": "   "}],
        },
    ],
)
def test_ask_rejects_invalid_questions_and_history_roles(client, payload):
    response = client.post("/api/ask", json=payload)
    assert response.status_code == 422


def test_ask_accepts_frontend_payload_and_hides_internal_failures(client, monkeypatch):
    class Pipeline:
        def __init__(self):
            self.call = None

        def answer_question(self, question, history, groq_api_key):
            self.call = (question, history, groq_api_key)
            return {"answer": "The answer", "sources": []}

    pipeline = Pipeline()
    monkeypatch.setattr(api, "pipeline", pipeline)
    response = client.post(
        "/api/ask",
        json={
            "question": "  What is this?  ",
            "chat_history": [{"role": "user", "content": " Earlier question "}],
        },
        headers={"x-groq-api-key": "test-only-key"},
    )

    assert response.status_code == 200
    assert response.json() == {"answer": "The answer", "sources": []}
    assert pipeline.call == (
        "What is this?",
        [{"role": "user", "content": "Earlier question"}],
        "test-only-key",
    )

    class FailingPipeline:
        def answer_question(self, *args, **kwargs):
            raise RuntimeError("private path: C:/users/example/secret.txt")

    monkeypatch.setattr(api, "pipeline", FailingPipeline())
    response = client.post(
        "/api/ask",
        json={"question": "What is this?", "chat_history": []},
    )
    assert response.status_code == 500
    assert response.json() == {"detail": "Unable to generate an answer."}
    assert "private path" not in response.text


@pytest.mark.parametrize("filename", ["notes.exe", "archive", "page.html"])
def test_upload_rejects_unsupported_extensions(client, filename):
    response = client.post(
        "/api/ingest",
        files={"file": (filename, b"content", "application/octet-stream")},
    )
    assert response.status_code == 415


def test_upload_rejects_empty_and_oversized_files(client, monkeypatch):
    response = client.post(
        "/api/ingest",
        files={"file": ("empty.txt", b"", "text/plain")},
    )
    assert response.status_code == 400
    assert response.json() == {"detail": "Uploaded file is empty."}

    monkeypatch.setattr(api, "MAX_UPLOAD_BYTES", 4)
    response = client.post(
        "/api/ingest",
        files={"file": ("large.txt", b"12345", "text/plain")},
    )
    assert response.status_code == 413


def test_upload_accepts_supported_file_and_sanitizes_its_name(client, monkeypatch):
    storage = RecordingStorage()

    def ingest_document(path):
        assert Path(path).suffix == ".txt"
        assert Path(path).read_bytes() == b"hello"
        return [SimpleNamespace(metadata={})]

    monkeypatch.setattr(api, "storage", storage)
    monkeypatch.setitem(
        sys.modules,
        "backend.app.ingestion",
        fake_ingestion_module(ingest_document=ingest_document),
    )

    response = client.post(
        "/api/ingest",
        files={"file": ("../notes.TXT", b"hello", "text/plain")},
    )

    assert response.status_code == 200
    assert response.json()["filename"] == "notes.TXT"
    assert response.json()["chunks"] == 1
    assert storage.added_chunks[0].metadata["source"] == "notes.TXT"


@pytest.mark.parametrize(
    "url",
    ["", "not a URL", "ftp://example.com/file", "file:///etc/passwd"],
)
def test_url_ingestion_rejects_non_http_urls(client, url):
    response = client.post("/api/ingest/url", json={"url": url})
    assert response.status_code == 422


def test_url_ingestion_accepts_http_url(client, monkeypatch):
    storage = RecordingStorage()

    def ingest_url(url):
        assert url == "https://example.com/article"
        return [SimpleNamespace(metadata={})]

    monkeypatch.setattr(api, "storage", storage)
    monkeypatch.setitem(
        sys.modules,
        "backend.app.ingestion",
        fake_ingestion_module(ingest_url=ingest_url),
    )

    response = client.post(
        "/api/ingest/url",
        json={"url": "https://example.com/article"},
    )

    assert response.status_code == 200
    assert response.json()["filename"] == "https://example.com/article"
    assert storage.added_chunks[0].metadata["source"] == ("https://example.com/article")


def test_empty_storage_returns_an_empty_document_list(client, monkeypatch):
    fake_client = SimpleNamespace(scroll=lambda **kwargs: ([], None))
    monkeypatch.setattr(
        api,
        "storage",
        SimpleNamespace(client=fake_client, collection_name="documents"),
    )

    response = client.get("/api/documents")
    assert response.status_code == 200
    assert response.json() == {"documents": []}


def test_history_is_validated_bounded_and_round_trips(client):
    history = [
        {
            "id": 1,
            "question": "What is Studio?",
            "answer": "A local RAG application.",
            "isSearching": False,
            "sources": [{"text": "Source text", "source": "notes.txt", "pages": [1]}],
        }
    ]

    response = client.post("/api/history", json=history)
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
    assert (
        json.loads(api.app.state.data_paths.history_file.read_text(encoding="utf-8"))
        == history
    )
    assert client.get("/api/history").json() == history

    invalid_entry = [{**history[0], "unexpected": "field"}]
    assert client.post("/api/history", json=invalid_entry).status_code == 422

    oversized_history = [
        {"id": index, "question": "question", "sources": []} for index in range(201)
    ]
    assert client.post("/api/history", json=oversized_history).status_code == 422
