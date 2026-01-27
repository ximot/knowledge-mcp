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

import httpx
import uvicorn
from starlette.applications import Starlette
from starlette.routing import Route
from starlette.responses import JSONResponse
from knowledge_mcp.server import mcp
from knowledge_mcp.config import settings


async def health_check(request):
    """
    Health check endpoint that verifies connectivity to Qdrant and Ollama.

    Returns JSON with status of each component.
    """
    health_status = {
        "status": "ok",
        "qdrant": False,
        "ollama": False,
        "model": settings.embedding_model
    }

    async with httpx.AsyncClient(timeout=5.0) as client:
        # Check Qdrant connectivity
        try:
            qdrant_url = f"{settings.qdrant_url}/collections"
            response = await client.get(qdrant_url)
            health_status["qdrant"] = response.status_code == 200
        except Exception as e:
            health_status["qdrant_error"] = str(e)

        # Check Ollama connectivity and model availability
        try:
            ollama_url = f"{settings.ollama_host}/api/tags"
            response = await client.get(ollama_url)
            if response.status_code == 200:
                data = response.json()
                models = [m.get("name", "") for m in data.get("models", [])]
                health_status["ollama"] = settings.embedding_model in models
                health_status["available_models"] = models
            else:
                health_status["ollama"] = False
        except Exception as e:
            health_status["ollama_error"] = str(e)

    # Overall status is ok only if both services are healthy
    if not (health_status["qdrant"] and health_status["ollama"]):
        health_status["status"] = "degraded"

    status_code = 200 if health_status["status"] == "ok" else 503
    return JSONResponse(health_status, status_code=status_code)


def main():
    port = int(os.getenv("MCP_PORT", "8765"))
    host = os.getenv("MCP_HOST", "0.0.0.0")

    print(f"Starting Knowledge MCP Server on {host}:{port}")
    print(f"  Qdrant: {os.getenv('QDRANT_HOST', 'localhost')}:{os.getenv('QDRANT_PORT', '6333')}")
    print(f"  Ollama: {os.getenv('OLLAMA_HOST', 'http://localhost:11434')}")
    print(f"  Endpoint: http://{host}:{port}/mcp")
    print(f"  Health: http://{host}:{port}/health")

    # Get the Starlette app from FastMCP and add health endpoint
    mcp_app = mcp.streamable_http_app()

    # Create a wrapper app that includes both MCP and health endpoints
    routes = [
        Route("/health", health_check, methods=["GET"]),
    ]

    # Mount the MCP app at /mcp and add our custom routes
    from starlette.middleware import Middleware
    from starlette.routing import Mount

    app = Starlette(
        routes=[
            *routes,
            Mount("/", mcp_app),
        ]
    )

    uvicorn.run(app, host=host, port=port)


if __name__ == "__main__":
    main()
