"""Tests for the Pydantic input models used by the MCP tools."""

import pytest
from pydantic import ValidationError

from knowledge_mcp.server import (
    KnowledgeAddInput,
    KnowledgeSearchInput,
    ProjectAddInput,
    SkillAddInput,
)


def test_knowledge_add_requires_title_and_content():
    with pytest.raises(ValidationError):
        KnowledgeAddInput(content="only content")

    with pytest.raises(ValidationError):
        KnowledgeAddInput(title="only title")


def test_knowledge_add_rejects_unknown_fields():
    with pytest.raises(ValidationError):
        KnowledgeAddInput(title="T", content="C", unexpected_field="nope")


def test_knowledge_add_strips_whitespace():
    entry = KnowledgeAddInput(title="  Title  ", content="  Content  ")
    assert entry.title == "Title"
    assert entry.content == "Content"


def test_knowledge_add_rejects_too_many_tags():
    with pytest.raises(ValidationError):
        KnowledgeAddInput(title="T", content="C", tags=[f"tag{i}" for i in range(21)])


def test_knowledge_add_defaults():
    entry = KnowledgeAddInput(title="T", content="C")
    assert entry.knowledge_type.value == "note"
    assert entry.tags == []
    assert entry.source is None


@pytest.mark.parametrize("limit", [0, 21, -1])
def test_knowledge_search_limit_out_of_bounds(limit):
    with pytest.raises(ValidationError):
        KnowledgeSearchInput(query="q", limit=limit)


@pytest.mark.parametrize("limit", [1, 5, 20])
def test_knowledge_search_limit_in_bounds(limit):
    assert KnowledgeSearchInput(query="q", limit=limit).limit == limit


def test_knowledge_search_requires_nonempty_query():
    with pytest.raises(ValidationError):
        KnowledgeSearchInput(query="")


@pytest.mark.parametrize("name", ["a", "a1", "code-review", "sql-expert-2"])
def test_skill_name_pattern_accepts_valid_slugs(name):
    skill = SkillAddInput(name=name, description="d", prompt="p")
    assert skill.name == name


@pytest.mark.parametrize(
    "name", ["Code-Review", "-leading-dash", "trailing-dash-", "has_underscore", ""]
)
def test_skill_name_pattern_rejects_invalid_slugs(name):
    with pytest.raises(ValidationError):
        SkillAddInput(name=name, description="d", prompt="p")


@pytest.mark.parametrize("name", ["a", "my-app", "data-pipeline-2"])
def test_project_name_pattern_accepts_valid_slugs(name):
    project = ProjectAddInput(name=name, description="d")
    assert project.name == name


@pytest.mark.parametrize("name", ["My-App", "_underscore", "double--dash-", ""])
def test_project_name_pattern_rejects_invalid_slugs(name):
    with pytest.raises(ValidationError):
        ProjectAddInput(name=name, description="d")


def test_project_add_defaults_to_active_status():
    project = ProjectAddInput(name="my-app", description="d")
    assert project.status.value == "active"
