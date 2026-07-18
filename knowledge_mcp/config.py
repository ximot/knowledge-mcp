"""
Configuration for Knowledge MCP Server.

Uses environment variables with sensible defaults for local development.
"""

import os
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class Settings:
    """Server configuration."""

    # Qdrant settings
    qdrant_host: str = field(default_factory=lambda: os.getenv("QDRANT_HOST", "localhost"))
    qdrant_port: int = field(default_factory=lambda: int(os.getenv("QDRANT_PORT", "6333")))
    qdrant_api_key: Optional[str] = field(default_factory=lambda: os.getenv("QDRANT_API_KEY"))
    qdrant_https: bool = field(
        default_factory=lambda: os.getenv("QDRANT_HTTPS", "false").lower() == "true"
    )

    # Ollama settings
    ollama_host: str = field(
        default_factory=lambda: os.getenv("OLLAMA_HOST", "http://localhost:11434")
    )
    embedding_model: str = field(
        default_factory=lambda: os.getenv("EMBEDDING_MODEL", "nomic-embed-text")
    )

    # Vector settings
    vector_size: int = field(default_factory=lambda: int(os.getenv("VECTOR_SIZE", "768")))

    # Optional bearer token required on /api/* and /mcp when set.
    # Leave unset for trusted-network-only deployments.
    auth_token: Optional[str] = field(default_factory=lambda: os.getenv("MCP_AUTH_TOKEN") or None)

    # Collection names
    knowledge_collection: str = "knowledge"
    skills_collection: str = "skills"
    projects_collection: str = "projects"
    private_collection: str = "private"

    @property
    def qdrant_url(self) -> str:
        """Full Qdrant URL."""
        protocol = "https" if self.qdrant_https else "http"
        return f"{protocol}://{self.qdrant_host}:{self.qdrant_port}"


# Global settings instance
settings = Settings()
