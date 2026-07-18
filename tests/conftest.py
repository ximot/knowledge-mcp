"""Shared pytest fixtures for the knowledge_mcp test suite."""

from unittest.mock import AsyncMock

import pytest

from knowledge_mcp.qdrant import QdrantService


@pytest.fixture
def mock_qdrant_client():
    """An AsyncMock standing in for AsyncQdrantClient."""
    return AsyncMock()


@pytest.fixture
def qdrant_service(mock_qdrant_client):
    """A QdrantService wired to a mock client, bypassing real connection setup."""
    service = QdrantService()
    service._client = mock_qdrant_client
    return service
