#!/usr/bin/env python3
"""
HTTP transport entry point for remote MCP access.

Serves the MCP protocol, a health check endpoint, a REST API for the
dashboard, and the dashboard static files.

Usage:
    PYTHONPATH=/path/to/knowledge-mcp python knowledge_mcp/http_server.py

Or with uv:
    uv run python knowledge_mcp/http_server.py
"""

import hashlib
import os
import sys
import time
from datetime import datetime
from pathlib import Path

# Add parent dir to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import httpx
import uvicorn
from starlette.applications import Starlette
from starlette.routing import Route, Mount
from starlette.responses import JSONResponse, HTMLResponse, FileResponse
from knowledge_mcp import __version__
from knowledge_mcp.server import mcp
from knowledge_mcp.config import settings
from knowledge_mcp.qdrant import QdrantService
from knowledge_mcp.embeddings import get_embeddings

# Shared Qdrant service for dashboard API
_qdrant = QdrantService()

# Server start time (epoch seconds)
_start_time = time.time()

# Path to dashboard directory (sibling of knowledge_mcp package)
DASHBOARD_DIR = Path(__file__).resolve().parent.parent / "dashboard"


# ---------------------------------------------------------------------------
# Health endpoint
# ---------------------------------------------------------------------------


async def health_check(request):
    """
    Health check endpoint that verifies connectivity to Qdrant and Ollama.

    Returns JSON with status of each component, version, uptime, and
    collection counts.
    """
    uptime_seconds = int(time.time() - _start_time)
    health_status = {
        "status": "ok",
        "version": __version__,
        "uptime_seconds": uptime_seconds,
        "qdrant": False,
        "ollama": False,
        "model": settings.embedding_model,
        "vector_size": settings.vector_size,
        "collections": {},
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
                health_status["ollama"] = any(
                    m == settings.embedding_model or m.startswith(f"{settings.embedding_model}:")
                    for m in models
                )
                health_status["available_models"] = models
            else:
                health_status["ollama"] = False
        except Exception as e:
            health_status["ollama_error"] = str(e)

    # Collection counts (best-effort)
    try:
        await _qdrant.ensure_collections()
        for name in [
            settings.knowledge_collection,
            settings.skills_collection,
            settings.projects_collection,
            settings.private_collection,
        ]:
            try:
                health_status["collections"][name] = (await _qdrant.client.count(name)).count
            except Exception:
                health_status["collections"][name] = 0
    except Exception:
        pass

    # Overall status is ok only if both services are healthy
    if not (health_status["qdrant"] and health_status["ollama"]):
        health_status["status"] = "degraded"

    status_code = 200 if health_status["status"] == "ok" else 503
    return JSONResponse(health_status, status_code=status_code)


# ---------------------------------------------------------------------------
# Dashboard REST API  (used by dashboard/index.html)
# ---------------------------------------------------------------------------


def _parse_tags(request) -> list[str]:
    """Parse a comma-separated ?tags= query param into a list (AND filter)."""
    raw = request.query_params.get("tags", "")
    return [t.strip() for t in raw.split(",") if t.strip()]


async def api_knowledge(request):
    """List or search knowledge entries, optionally filtered by tags (AND)."""
    await _qdrant.ensure_collections()
    query = request.query_params.get("q", "")
    limit = min(int(request.query_params.get("limit", "50")), 200)
    tags = _parse_tags(request)
    filters = {"tags": tags} if tags else None

    if query:
        vector = await get_embeddings(query)
        results = await _qdrant.search(
            settings.knowledge_collection, vector, limit=limit, filters=filters
        )
        return JSONResponse({"results": results, "count": len(results)})

    results, total = await _qdrant.list_all(
        settings.knowledge_collection, limit=limit, filters=filters
    )
    return JSONResponse({"results": results, "count": total})


async def api_knowledge_add(request):
    """Add a knowledge entry via POST."""
    body = await request.json()
    title = body.get("title", "").strip()
    content = body.get("content", "").strip()
    if not title or not content:
        return JSONResponse(
            {"success": False, "error": "title and content required"},
            status_code=400,
        )

    kid = f"k-{hashlib.sha256((title + content).encode()).hexdigest()[:12]}"
    now = datetime.utcnow().isoformat()
    payload = {
        "id": kid,
        "title": title,
        "content": content,
        "knowledge_type": body.get("knowledge_type", "note"),
        "tags": body.get("tags", []),
        "source": body.get("source"),
        "metadata": {},
        "created_at": now,
        "updated_at": now,
    }
    vector = await get_embeddings(f"{title} {content}")
    await _qdrant.upsert(settings.knowledge_collection, kid, vector, payload)
    return JSONResponse({"success": True, "id": kid})


async def api_knowledge_delete(request):
    """Delete a knowledge entry by ID."""
    entry_id = request.path_params["id"]
    existing = await _qdrant.get_by_id(settings.knowledge_collection, entry_id)
    if not existing:
        return JSONResponse({"success": False, "error": "not found"}, status_code=404)
    await _qdrant.delete(settings.knowledge_collection, entry_id)
    return JSONResponse({"success": True, "id": entry_id})


async def api_skills(request):
    """List or search skills, optionally filtered by tags (AND)."""
    await _qdrant.ensure_collections()
    query = request.query_params.get("q", "")
    limit = min(int(request.query_params.get("limit", "50")), 200)
    tags = _parse_tags(request)
    filters = {"tags": tags} if tags else None

    if query:
        vector = await get_embeddings(query)
        results = await _qdrant.search(
            settings.skills_collection, vector, limit=limit, filters=filters
        )
        return JSONResponse({"results": results, "count": len(results)})

    results, total = await _qdrant.list_all(
        settings.skills_collection, limit=limit, filters=filters
    )
    return JSONResponse({"results": results, "count": total})


async def api_skill_add(request):
    """Add a skill via POST."""
    body = await request.json()
    name = body.get("name", "").strip()
    prompt = body.get("prompt", "").strip()
    if not name or not prompt:
        return JSONResponse(
            {"success": False, "error": "name and prompt required"},
            status_code=400,
        )

    sid = f"s-{name}"
    now = datetime.utcnow().isoformat()
    payload = {
        "id": sid,
        "name": name,
        "description": body.get("description", ""),
        "prompt": prompt,
        "tags": body.get("tags", []),
        "version": body.get("version", "1.0.0"),
        "examples": [],
        "created_at": now,
        "updated_at": now,
    }
    vector = await get_embeddings(f"{name} {body.get('description', '')} {prompt}")
    await _qdrant.ensure_collections()
    await _qdrant.upsert(settings.skills_collection, sid, vector, payload)
    return JSONResponse({"success": True, "id": sid})


async def api_skill_delete(request):
    """Delete a skill by ID."""
    entry_id = request.path_params["id"]
    existing = await _qdrant.get_by_id(settings.skills_collection, entry_id)
    if not existing:
        return JSONResponse({"success": False, "error": "not found"}, status_code=404)
    await _qdrant.delete(settings.skills_collection, entry_id)
    return JSONResponse({"success": True, "id": entry_id})


async def api_projects(request):
    """List or search projects, optionally filtered by tags (AND)."""
    await _qdrant.ensure_collections()
    query = request.query_params.get("q", "")
    limit = min(int(request.query_params.get("limit", "50")), 200)
    tags = _parse_tags(request)
    filters = {"tags": tags} if tags else None

    if query:
        vector = await get_embeddings(query)
        results = await _qdrant.search(
            settings.projects_collection, vector, limit=limit, filters=filters
        )
        return JSONResponse({"results": results, "count": len(results)})

    results, total = await _qdrant.list_all(
        settings.projects_collection, limit=limit, filters=filters
    )
    return JSONResponse({"results": results, "count": total})


async def api_project_add(request):
    """Add a project via POST."""
    body = await request.json()
    name = body.get("name", "").strip()
    description = body.get("description", "").strip()
    if not name:
        return JSONResponse(
            {"success": False, "error": "name is required"},
            status_code=400,
        )

    pid = f"p-{name}"
    now = datetime.utcnow().isoformat()
    payload = {
        "id": pid,
        "name": name,
        "path": body.get("path", ""),
        "description": description,
        "status": body.get("status", "active"),
        "tags": body.get("tags", []),
        "metadata": body.get("metadata", {}),
        "created_at": now,
        "updated_at": now,
    }
    vector = await get_embeddings(f"{name} {description}")
    await _qdrant.ensure_collections()
    await _qdrant.upsert(settings.projects_collection, pid, vector, payload)
    return JSONResponse({"success": True, "id": pid})


async def api_project_delete(request):
    """Delete a project by ID."""
    entry_id = request.path_params["id"]
    existing = await _qdrant.get_by_id(settings.projects_collection, entry_id)
    if not existing:
        return JSONResponse({"success": False, "error": "not found"}, status_code=404)
    await _qdrant.delete(settings.projects_collection, entry_id)
    return JSONResponse({"success": True, "id": entry_id})


async def api_private(request):
    """List or search private entries, optionally filtered by tags (AND)."""
    await _qdrant.ensure_collections()
    query = request.query_params.get("q", "")
    limit = min(int(request.query_params.get("limit", "50")), 200)
    tags = _parse_tags(request)
    filters = {"tags": tags} if tags else None

    if query:
        vector = await get_embeddings(query)
        results = await _qdrant.search(
            settings.private_collection, vector, limit=limit, filters=filters
        )
        return JSONResponse({"results": results, "count": len(results)})

    results, total = await _qdrant.list_all(
        settings.private_collection, limit=limit, filters=filters
    )
    return JSONResponse({"results": results, "count": total})


async def api_private_add(request):
    """Add a private entry via POST."""
    body = await request.json()
    title = body.get("title", "").strip()
    content = body.get("content", "").strip()
    if not title or not content:
        return JSONResponse(
            {"success": False, "error": "title and content required"},
            status_code=400,
        )

    priv_id = f"priv-{hashlib.sha256((title + content).encode()).hexdigest()[:12]}"
    now = datetime.utcnow().isoformat()
    payload = {
        "id": priv_id,
        "title": title,
        "content": content,
        "private_type": body.get("private_type", "note"),
        "tags": body.get("tags", []),
        "metadata": body.get("metadata", {}),
        "created_at": now,
        "updated_at": now,
    }
    vector = await get_embeddings(f"{title} {content}")
    await _qdrant.ensure_collections()
    await _qdrant.upsert(settings.private_collection, priv_id, vector, payload)
    return JSONResponse({"success": True, "id": priv_id})


async def api_private_delete(request):
    """Delete a private entry by ID."""
    entry_id = request.path_params["id"]
    existing = await _qdrant.get_by_id(settings.private_collection, entry_id)
    if not existing:
        return JSONResponse({"success": False, "error": "not found"}, status_code=404)
    await _qdrant.delete(settings.private_collection, entry_id)
    return JSONResponse({"success": True, "id": entry_id})


async def api_stats(request):
    """Quick stats for the dashboard header."""
    await _qdrant.ensure_collections()
    try:
        k_count = (await _qdrant.client.count(settings.knowledge_collection)).count
    except Exception:
        k_count = 0
    try:
        s_count = (await _qdrant.client.count(settings.skills_collection)).count
    except Exception:
        s_count = 0
    try:
        p_count = (await _qdrant.client.count(settings.projects_collection)).count
    except Exception:
        p_count = 0
    try:
        pr_count = (await _qdrant.client.count(settings.private_collection)).count
    except Exception:
        pr_count = 0
    return JSONResponse(
        {
            "knowledge_count": k_count,
            "skills_count": s_count,
            "projects_count": p_count,
            "private_count": pr_count,
            "active_sessions": 0,
        }
    )


async def api_graph(request):
    """Build a tag-based graph of knowledge and skills for vis.js."""
    await _qdrant.ensure_collections()

    nodes = []
    edges = []
    tag_stats: dict[str, int] = {}
    tag_to_node_ids: dict[str, list[str]] = {}

    # Fetch knowledge entries
    k_results, _ = await _qdrant.list_all(settings.knowledge_collection, limit=200)
    for item in k_results:
        node_id = item.get("id", "")
        nodes.append(
            {
                "id": node_id,
                "label": item.get("title", node_id[:10]),
                "type": "knowledge",
                "title": item.get("title", ""),
                "description": item.get("content", "")[:200],
                "knowledge_type": item.get("knowledge_type", ""),
                "tags": item.get("tags", []),
            }
        )
        for tag in item.get("tags", []):
            tag_stats[tag] = tag_stats.get(tag, 0) + 1
            tag_to_node_ids.setdefault(tag, []).append(node_id)

    # Fetch skills
    s_results, _ = await _qdrant.list_all(settings.skills_collection, limit=200)
    for item in s_results:
        node_id = item.get("id", "")
        nodes.append(
            {
                "id": node_id,
                "label": item.get("name", node_id[:10]),
                "type": "skill",
                "title": item.get("name", ""),
                "description": item.get("description", ""),
                "tags": item.get("tags", []),
            }
        )
        for tag in item.get("tags", []):
            tag_stats[tag] = tag_stats.get(tag, 0) + 1
            tag_to_node_ids.setdefault(tag, []).append(node_id)

    # Build edges: nodes sharing tags
    edge_map: dict[tuple[str, str], list[str]] = {}
    for tag, nids in tag_to_node_ids.items():
        for i in range(len(nids)):
            for j in range(i + 1, len(nids)):
                key = (min(nids[i], nids[j]), max(nids[i], nids[j]))
                edge_map.setdefault(key, []).append(tag)

    for (a, b), tags in edge_map.items():
        edges.append({"from": a, "to": b, "tags": tags})

    # Tag hub nodes, one per tag, connected to every item carrying that tag —
    # lets the dashboard offer "click a tag to filter" on the graph view.
    for tag, count in tag_stats.items():
        nodes.append(
            {
                "id": f"tag:{tag}",
                "label": f"#{tag}",
                "type": "tag",
                "tag": tag,
                "count": count,
            }
        )
    for tag, node_ids in tag_to_node_ids.items():
        for node_id in node_ids:
            edges.append({"from": f"tag:{tag}", "to": node_id, "tags": [tag], "isTagEdge": True})

    return JSONResponse(
        {
            "nodes": nodes,
            "edges": edges,
            "tag_stats": tag_stats,
        }
    )


# ---------------------------------------------------------------------------
# Dashboard static files
# ---------------------------------------------------------------------------


async def dashboard_index(request):
    """Serve dashboard/index.html."""
    index_path = DASHBOARD_DIR / "index.html"
    if index_path.is_file():
        return FileResponse(str(index_path), media_type="text/html")
    return HTMLResponse(
        "<h1>Dashboard not found</h1><p>No dashboard/index.html</p>",
        status_code=404,
    )


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main():
    port = int(os.getenv("MCP_PORT", "8765"))
    host = os.getenv("MCP_HOST", "0.0.0.0")

    print(f"Starting Knowledge MCP Server on {host}:{port}")
    print(f"  Qdrant: {os.getenv('QDRANT_HOST', 'localhost')}:{os.getenv('QDRANT_PORT', '6333')}")
    print(f"  Ollama: {os.getenv('OLLAMA_HOST', 'http://localhost:11434')}")
    print(f"  Endpoint: http://{host}:{port}/mcp")
    print(f"  Health: http://{host}:{port}/health")
    print(f"  Dashboard: http://{host}:{port}/dashboard")

    # Get the Starlette app from FastMCP
    mcp_app = mcp.streamable_http_app()

    # Routes
    routes = [
        Route("/health", health_check, methods=["GET"]),
        # Dashboard REST API
        Route("/api/knowledge", api_knowledge, methods=["GET"]),
        Route("/api/knowledge", api_knowledge_add, methods=["POST"]),
        Route("/api/knowledge/{id}", api_knowledge_delete, methods=["DELETE"]),
        Route("/api/skills", api_skills, methods=["GET"]),
        Route("/api/skills", api_skill_add, methods=["POST"]),
        Route("/api/skills/{id}", api_skill_delete, methods=["DELETE"]),
        Route("/api/projects", api_projects, methods=["GET"]),
        Route("/api/projects", api_project_add, methods=["POST"]),
        Route("/api/projects/{id}", api_project_delete, methods=["DELETE"]),
        Route("/api/private", api_private, methods=["GET"]),
        Route("/api/private", api_private_add, methods=["POST"]),
        Route("/api/private/{id}", api_private_delete, methods=["DELETE"]),
        Route("/api/stats", api_stats, methods=["GET"]),
        Route("/api/graph", api_graph, methods=["GET"]),
        # Dashboard UI
        Route("/dashboard", dashboard_index, methods=["GET"]),
        Route("/dashboard/", dashboard_index, methods=["GET"]),
        # MCP protocol (catch-all mount)
        Mount("/", mcp_app),
    ]

    app = Starlette(routes=routes)

    uvicorn.run(app, host=host, port=port)


if __name__ == "__main__":
    main()
