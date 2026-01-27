"""
Knowledge MCP Server — self-hosted RAG knowledge base for AI coding assistants.

Provides a shared knowledge base and skills repository
accessible from any MCP-compatible client.
"""

from .server import mcp, main
from .config import settings

__version__ = "0.1.0"
__all__ = ["mcp", "main", "settings"]
