"""Tests for Settings env-var driven configuration."""

import importlib

from knowledge_mcp import config


def reload_settings():
    """Re-import config so field(default_factory=...) re-reads os.environ."""
    importlib.reload(config)
    return config.Settings()


def test_defaults(monkeypatch):
    for var in (
        "QDRANT_HOST",
        "QDRANT_PORT",
        "QDRANT_API_KEY",
        "QDRANT_HTTPS",
        "OLLAMA_HOST",
        "EMBEDDING_MODEL",
        "VECTOR_SIZE",
    ):
        monkeypatch.delenv(var, raising=False)

    settings = reload_settings()

    assert settings.qdrant_host == "localhost"
    assert settings.qdrant_port == 6333
    assert settings.qdrant_api_key is None
    assert settings.qdrant_https is False
    assert settings.ollama_host == "http://localhost:11434"
    assert settings.embedding_model == "nomic-embed-text"
    assert settings.vector_size == 768


def test_env_overrides(monkeypatch):
    monkeypatch.setenv("QDRANT_HOST", "qdrant.internal")
    monkeypatch.setenv("QDRANT_PORT", "7000")
    monkeypatch.setenv("QDRANT_API_KEY", "secret-key")
    monkeypatch.setenv("QDRANT_HTTPS", "true")
    monkeypatch.setenv("OLLAMA_HOST", "http://ollama.internal:11434")
    monkeypatch.setenv("EMBEDDING_MODEL", "custom-model")
    monkeypatch.setenv("VECTOR_SIZE", "1536")

    settings = reload_settings()

    assert settings.qdrant_host == "qdrant.internal"
    assert settings.qdrant_port == 7000
    assert settings.qdrant_api_key == "secret-key"
    assert settings.qdrant_https is True
    assert settings.ollama_host == "http://ollama.internal:11434"
    assert settings.embedding_model == "custom-model"
    assert settings.vector_size == 1536


def test_qdrant_https_is_case_insensitive(monkeypatch):
    monkeypatch.setenv("QDRANT_HTTPS", "TRUE")
    assert reload_settings().qdrant_https is True

    monkeypatch.setenv("QDRANT_HTTPS", "false")
    assert reload_settings().qdrant_https is False


def test_qdrant_url_reflects_protocol(monkeypatch):
    monkeypatch.setenv("QDRANT_HOST", "myhost")
    monkeypatch.setenv("QDRANT_PORT", "1234")

    monkeypatch.setenv("QDRANT_HTTPS", "false")
    assert reload_settings().qdrant_url == "http://myhost:1234"

    monkeypatch.setenv("QDRANT_HTTPS", "true")
    assert reload_settings().qdrant_url == "https://myhost:1234"


def test_collection_names_are_fixed(monkeypatch):
    settings = reload_settings()
    assert settings.knowledge_collection == "knowledge"
    assert settings.skills_collection == "skills"
    assert settings.projects_collection == "projects"
    assert settings.private_collection == "private"
