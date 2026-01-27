#!/usr/bin/env python3
"""
HTTP transport entry point for remote MCP access.

Usage:
    PYTHONPATH=/path/to/knowledge-mcp python knowledge_mcp/http_server.py

Or with uv:
    uv run python knowledge_mcp/http_server.py
"""

import os
import sys

# Add parent dir to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import uvicorn
from knowledge_mcp.server import mcp


def main():
    port = int(os.getenv("MCP_PORT", "8765"))
    host = os.getenv("MCP_HOST", "0.0.0.0")

    print(f"Starting Knowledge MCP Server on {host}:{port}")
    print(f"  Qdrant: {os.getenv('QDRANT_HOST', 'localhost')}:{os.getenv('QDRANT_PORT', '6333')}")
    print(f"  Ollama: {os.getenv('OLLAMA_HOST', 'http://localhost:11434')}")
    print(f"  Endpoint: http://{host}:{port}/mcp")

    # Get the Starlette app from FastMCP
    app = mcp.streamable_http_app()

    uvicorn.run(app, host=host, port=port)


if __name__ == "__main__":
    main()
