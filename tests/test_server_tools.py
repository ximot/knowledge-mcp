"""Integration-style tests for MCP tool functions, mocking Qdrant and embeddings."""

import hashlib
import json
from unittest.mock import AsyncMock

import pytest

from knowledge_mcp import server
from knowledge_mcp.server import (
    KnowledgeAddInput,
    KnowledgeDeleteInput,
    KnowledgeGetInput,
    KnowledgeSearchInput,
    ProjectAddInput,
    ResponseFormat,
    SkillAddInput,
    knowledge_add,
    knowledge_delete,
    knowledge_get,
    knowledge_search,
    project_add,
    skill_add,
)


@pytest.fixture(autouse=True)
def fake_embeddings(monkeypatch):
    mock = AsyncMock(return_value=[0.1, 0.2, 0.3])
    monkeypatch.setattr(server, "get_embeddings", mock)
    return mock


@pytest.fixture
def fake_qdrant(monkeypatch):
    mock = AsyncMock()
    monkeypatch.setattr(server, "qdrant", mock)
    return mock


async def test_knowledge_add_generates_content_hash_id(fake_qdrant, fake_embeddings):
    params = KnowledgeAddInput(title="My Title", content="My Content")

    result = await knowledge_add(params)

    expected_hash = hashlib.sha256(b"My TitleMy Content").hexdigest()[:12]
    expected_id = f"k-{expected_hash}"
    assert expected_id in result

    fake_qdrant.upsert.assert_awaited_once()
    kwargs = fake_qdrant.upsert.await_args.kwargs
    assert kwargs["id"] == expected_id
    assert kwargs["payload"]["title"] == "My Title"
    assert kwargs["vector"] == [0.1, 0.2, 0.3]


async def test_knowledge_add_embeds_title_and_content(fake_qdrant, fake_embeddings):
    await knowledge_add(KnowledgeAddInput(title="T", content="C"))
    fake_embeddings.assert_awaited_once_with("T\n\nC")


async def test_knowledge_add_returns_error_string_on_failure(fake_qdrant, fake_embeddings):
    fake_qdrant.upsert.side_effect = RuntimeError("qdrant down")

    result = await knowledge_add(KnowledgeAddInput(title="T", content="C"))

    assert "Error adding knowledge entry" in result
    assert "qdrant down" in result


async def test_knowledge_search_returns_message_when_empty(fake_qdrant, fake_embeddings):
    fake_qdrant.search.return_value = []
    result = await knowledge_search(KnowledgeSearchInput(query="anything"))
    assert result == "No matching knowledge entries found."


async def test_knowledge_search_json_format(fake_qdrant, fake_embeddings):
    fake_qdrant.search.return_value = [{"title": "A", "score": 0.9}]

    result = await knowledge_search(
        KnowledgeSearchInput(query="anything", response_format=ResponseFormat.JSON)
    )

    parsed = json.loads(result)
    assert parsed == [{"title": "A", "score": 0.9}]


async def test_knowledge_search_passes_tag_filters(fake_qdrant, fake_embeddings):
    fake_qdrant.search.return_value = []
    await knowledge_search(KnowledgeSearchInput(query="q", tags=["python", "mcp"]))

    kwargs = fake_qdrant.search.await_args.kwargs
    assert kwargs["filters"]["tags"] == ["python", "mcp"]


async def test_knowledge_get_not_found(fake_qdrant):
    fake_qdrant.get_by_id.return_value = None
    result = await knowledge_get(KnowledgeGetInput(id="k-missing"))
    assert "not found" in result


async def test_knowledge_get_found_markdown(fake_qdrant):
    fake_qdrant.get_by_id.return_value = {
        "title": "Found",
        "content": "Body",
        "knowledge_type": "note",
        "tags": [],
    }
    result = await knowledge_get(KnowledgeGetInput(id="k-abc"))
    assert "Found" in result
    assert "Body" in result


async def test_knowledge_delete_not_found(fake_qdrant):
    fake_qdrant.get_by_id.return_value = None
    result = await knowledge_delete(KnowledgeDeleteInput(id="k-missing"))
    assert "not found" in result
    fake_qdrant.delete.assert_not_awaited()


async def test_knowledge_delete_success(fake_qdrant):
    fake_qdrant.get_by_id.return_value = {"title": "Existing"}
    result = await knowledge_delete(KnowledgeDeleteInput(id="k-abc"))
    assert "deleted successfully" in result
    fake_qdrant.delete.assert_awaited_once_with(collection="knowledge", id="k-abc")


async def test_skill_add_uses_name_as_id(fake_qdrant, fake_embeddings):
    fake_qdrant.get_by_field.return_value = None

    result = await skill_add(SkillAddInput(name="code-review", description="d", prompt="p"))

    assert "created successfully" in result
    kwargs = fake_qdrant.upsert.await_args.kwargs
    assert kwargs["id"] == "s-code-review"


async def test_skill_add_rejects_duplicate_name(fake_qdrant, fake_embeddings):
    fake_qdrant.get_by_field.return_value = {"name": "code-review"}

    result = await skill_add(SkillAddInput(name="code-review", description="d", prompt="p"))

    assert "already exists" in result
    fake_qdrant.upsert.assert_not_awaited()


async def test_project_add_uses_name_as_id(fake_qdrant, fake_embeddings):
    fake_qdrant.get_by_field.return_value = None

    result = await project_add(ProjectAddInput(name="my-app", description="d"))

    assert "created successfully" in result
    kwargs = fake_qdrant.upsert.await_args.kwargs
    assert kwargs["id"] == "p-my-app"
