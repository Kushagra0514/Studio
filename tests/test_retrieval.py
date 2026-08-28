import sys
from types import ModuleType, SimpleNamespace

import pytest

from backend.app import retrieval


class RecordingStorage:
    def __init__(self, results=()):
        self.results = list(results)
        self.calls = []

    def search(self, query, limit):
        self.calls.append((query, limit))
        return self.results


def install_fake_llm(monkeypatch, *outcomes):
    outcomes = list(outcomes)

    def create(**kwargs):
        outcome = outcomes.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        return SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content=outcome))]
        )

    client = SimpleNamespace(
        chat=SimpleNamespace(completions=SimpleNamespace(create=create))
    )
    monkeypatch.setattr(retrieval, "Groq", lambda **kwargs: client)


def test_router_failure_falls_back_without_hiding_generation_failure(monkeypatch):
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    storage = RecordingStorage()
    install_fake_llm(
        monkeypatch,
        RuntimeError("router unavailable"),
        RuntimeError("generation unavailable"),
    )

    pipeline = retrieval.RetrievalPipeline(storage)
    with pytest.raises(RuntimeError, match="generation unavailable"):
        pipeline.answer_question("original question")

    assert storage.calls == [("original question", 10)]


def test_web_search_failure_falls_back_to_local_search(monkeypatch):
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    monkeypatch.delenv("FIRECRAWL_API_KEY", raising=False)
    local_result = SimpleNamespace(
        payload={"text": "Local context", "source": "notes.txt"}
    )
    storage = RecordingStorage([local_result])
    install_fake_llm(
        monkeypatch,
        '{"intent":"WEB_SEARCH","query":"rewritten question"}',
        "Local answer [1]",
    )

    firecrawl = ModuleType("firecrawl")

    class FailingFirecrawlApp:
        def __init__(self, **kwargs):
            pass

        def search(self, query):
            raise RuntimeError("firecrawl unavailable")

    firecrawl.FirecrawlApp = FailingFirecrawlApp
    monkeypatch.setitem(sys.modules, "firecrawl", firecrawl)

    result = retrieval.RetrievalPipeline(storage).answer_question("original question")

    assert storage.calls == [("rewritten question", 10)]
    assert result == {"answer": "Local answer [1]", "sources": [local_result]}
