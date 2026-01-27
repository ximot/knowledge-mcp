"""
Knowledge MCP Server - Centralny RAG dla Claude Code.

Provides a shared knowledge base and skills repository
accessible from any Claude Code instance.
"""

from .server import mcp, main
from .config import settings

__version__ = "1.0.0"
__all__ = ["mcp", "main", "settings"]
