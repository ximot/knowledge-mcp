"""Tests for the Ollama embeddings client."""

import pytest

from knowledge_mcp.embeddings import get_embeddings, get_embeddings_batch


class FakeResponse:
    def __init__(self, embedding):
        self._embedding = embedding

    def raise_for_status(self):
        pass

    def json(self):
        return {"embedding": self._embedding}


class FakeAsyncClient:
    """Stands in for httpx.AsyncClient, recording the last request made."""

    last_instance = None

    def __init__(self, *args, **kwargs):
        self.post_calls = []
        FakeAsyncClient.last_instance = self

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc_info):
        return False

    async def post(self, url, json):
        self.post_calls.append((url, json))
        return FakeResponse([0.1, 0.2, 0.3])


@pytest.fixture(autouse=True)
def fake_httpx(monkeypatch):
    monkeypatch.setattr("knowledge_mcp.embeddings.httpx.AsyncClient", FakeAsyncClient)


async def test_get_embeddings_returns_vector():
    result = await get_embeddings("hello world")
    assert result == [0.1, 0.2, 0.3]


async def test_get_embeddings_sends_model_and_prompt():
    await get_embeddings("hello world")
    url, payload = FakeAsyncClient.last_instance.post_calls[0]
    assert url.endswith("/api/embeddings")
    assert payload["prompt"] == "hello world"
    assert "model" in payload


async def test_get_embeddings_truncates_long_text():
    long_text = "a" * 9000
    await get_embeddings(long_text)
    _, payload = FakeAsyncClient.last_instance.post_calls[0]
    assert len(payload["prompt"]) == 8000


async def test_get_embeddings_batch_calls_once_per_text():
    texts = ["one", "two", "three"]
    results = await get_embeddings_batch(texts)

    assert len(results) == 3
    assert all(r == [0.1, 0.2, 0.3] for r in results)
