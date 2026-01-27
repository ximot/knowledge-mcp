#!/usr/bin/env python3
"""
Simple REST API for n8n and other integrations.

Endpoints:
  POST /api/knowledge - add knowledge entry
  GET  /api/knowledge - list/search knowledge
  POST /api/skills    - add skill
  GET  /api/skills    - list skills
"""

import os
import sys
import hashlib
import time
from datetime import datetime
from typing import Optional, List, Dict

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import uvicorn
from starlette.applications import Starlette
from starlette.routing import Route, Mount
from starlette.requests import Request
from starlette.responses import JSONResponse, FileResponse
from starlette.staticfiles import StaticFiles
from starlette.middleware import Middleware
from starlette.middleware.cors import CORSMiddleware

from knowledge_mcp.config import settings
from knowledge_mcp.embeddings import get_embeddings
from knowledge_mcp.qdrant import QdrantService

qdrant = QdrantService()

# ============================================================================
# Session Tracking (simple in-memory with TTL)
# ============================================================================
SESSION_TTL = 60  # seconds - session expires after 60s of inactivity
active_sessions: Dict[str, float] = {}  # session_id -> last_seen timestamp


def cleanup_sessions():
    """Remove expired sessions."""
    now = time.time()
    expired = [sid for sid, ts in active_sessions.items() if now - ts > SESSION_TTL]
    for sid in expired:
        del active_sessions[sid]


def track_session(request: Request) -> str:
    """Track session from request, returns session_id."""
    # Use X-Session-ID header or generate from IP + User-Agent
    session_id = request.headers.get("X-Session-ID")
    if not session_id:
        client_ip = request.client.host if request.client else "unknown"
        user_agent = request.headers.get("User-Agent", "")[:50]
        session_id = hashlib.md5(f"{client_ip}:{user_agent}".encode()).hexdigest()[:12]

    active_sessions[session_id] = time.time()
    cleanup_sessions()
    return session_id


async def add_knowledge(request: Request) -> JSONResponse:
    """
    POST /api/knowledge
    Body: {
        "title": "...",
        "content": "...",
        "knowledge_type": "note|documentation|code_snippet|reference|howto|other",
        "tags": ["tag1", "tag2"],
        "source": "optional url"
    }
    """
    try:
        data = await request.json()

        title = data.get("title", "").strip()
        content = data.get("content", "").strip()

        if not title or not content:
            return JSONResponse({"error": "title and content are required"}, status_code=400)

        knowledge_type = data.get("knowledge_type", "note")
        tags = data.get("tags", [])
        source = data.get("source")
        metadata = data.get("metadata", {})

        # Generate ID
        content_hash = hashlib.sha256(f"{title}{content}".encode()).hexdigest()[:12]
        entry_id = f"k-{content_hash}"

        # Get embeddings
        text_for_embedding = f"{title}\n\n{content}"
        embedding = await get_embeddings(text_for_embedding)

        # Payload
        payload = {
            "id": entry_id,
            "title": title,
            "content": content,
            "knowledge_type": knowledge_type,
            "tags": tags if isinstance(tags, list) else [t.strip() for t in tags.split(",")],
            "source": source,
            "metadata": metadata,
            "created_at": datetime.utcnow().isoformat(),
            "updated_at": datetime.utcnow().isoformat()
        }

        await qdrant.upsert(collection="knowledge", id=entry_id, vector=embedding, payload=payload)

        return JSONResponse({"success": True, "id": entry_id, "title": title})

    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


async def list_knowledge(request: Request) -> JSONResponse:
    """
    GET /api/knowledge
    Query params:
        q: search query (semantic search)
        limit: max results (default 10)
        tags: comma-separated tags filter
    """
    try:
        query = request.query_params.get("q", "")
        limit = int(request.query_params.get("limit", "10"))
        tags_param = request.query_params.get("tags", "")

        filters = {}
        if tags_param:
            filters["tags"] = [t.strip() for t in tags_param.split(",")]

        if query:
            # Semantic search
            embedding = await get_embeddings(query)
            results = await qdrant.search(
                collection="knowledge",
                vector=embedding,
                limit=limit,
                filters=filters if filters else None
            )
        else:
            # List all
            results, _ = await qdrant.list_all(
                collection="knowledge",
                limit=limit,
                filters=filters if filters else None
            )

        return JSONResponse({"results": results, "count": len(results)})

    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


async def add_skill(request: Request) -> JSONResponse:
    """
    POST /api/skills
    Body: {
        "name": "skill-name",
        "description": "...",
        "prompt": "...",
        "tags": ["tag1"],
        "version": "1.0.0"
    }
    """
    try:
        data = await request.json()

        name = data.get("name", "").strip().lower()
        description = data.get("description", "").strip()
        prompt = data.get("prompt", "").strip()

        if not name or not description or not prompt:
            return JSONResponse({"error": "name, description and prompt are required"}, status_code=400)

        tags = data.get("tags", [])
        version = data.get("version", "1.0.0")
        examples = data.get("examples", [])

        skill_id = f"s-{name}"

        # Check if exists
        existing = await qdrant.get_by_field(collection="skills", field="name", value=name)
        if existing:
            return JSONResponse({"error": f"Skill '{name}' already exists"}, status_code=409)

        # Embedding
        text_for_embedding = f"{name}\n{description}\n{prompt}"
        embedding = await get_embeddings(text_for_embedding)

        payload = {
            "id": skill_id,
            "name": name,
            "description": description,
            "prompt": prompt,
            "tags": tags if isinstance(tags, list) else [t.strip() for t in tags.split(",")],
            "version": version,
            "examples": examples,
            "created_at": datetime.utcnow().isoformat(),
            "updated_at": datetime.utcnow().isoformat()
        }

        await qdrant.upsert(collection="skills", id=skill_id, vector=embedding, payload=payload)

        return JSONResponse({"success": True, "id": skill_id, "name": name})

    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


async def list_skills(request: Request) -> JSONResponse:
    """
    GET /api/skills
    Query params:
        q: search query
        limit: max results
    """
    try:
        query = request.query_params.get("q", "")
        limit = int(request.query_params.get("limit", "20"))

        if query:
            embedding = await get_embeddings(query)
            results = await qdrant.search(collection="skills", vector=embedding, limit=limit)
        else:
            results, _ = await qdrant.list_all(collection="skills", limit=limit)

        # Remove full prompt from list view
        for r in results:
            r.pop("prompt", None)

        return JSONResponse({"results": results, "count": len(results)})

    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


async def health(request: Request) -> JSONResponse:
    """GET /health"""
    return JSONResponse({"status": "ok"})


async def stats(request: Request) -> JSONResponse:
    """GET /api/stats - quick stats for dashboard"""
    track_session(request)  # Track this session
    try:
        knowledge, k_total = await qdrant.list_all(collection="knowledge", limit=1)
        skills, s_total = await qdrant.list_all(collection="skills", limit=1)
        cleanup_sessions()
        return JSONResponse({
            "knowledge_count": k_total,
            "skills_count": s_total,
            "active_sessions": len(active_sessions)
        })
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


async def sessions(request: Request) -> JSONResponse:
    """GET /api/sessions - active sessions info"""
    track_session(request)
    cleanup_sessions()
    now = time.time()
    session_list = [
        {
            "id": sid,
            "last_seen_ago": int(now - ts),
            "expires_in": max(0, int(SESSION_TTL - (now - ts)))
        }
        for sid, ts in active_sessions.items()
    ]
    return JSONResponse({
        "active_count": len(active_sessions),
        "ttl_seconds": SESSION_TTL,
        "sessions": session_list
    })


async def status(request: Request) -> JSONResponse:
    """GET /api/status - check all services"""
    import httpx

    results = {
        "rest_api": True,  # We're responding, so it's up
        "mcp": False,
        "qdrant": False,
        "ollama": False
    }

    async with httpx.AsyncClient(timeout=5.0) as client:
        # Check MCP
        try:
            mcp_host = os.getenv("MCP_HOST", "localhost")
            mcp_port = os.getenv("MCP_PORT", "8765")
            res = await client.get(f"http://{mcp_host}:{mcp_port}/mcp")
            # 200 = OK, 406 = server running but missing Accept header (still alive)
            results["mcp"] = res.status_code in (200, 406)
        except:
            pass

        # Check Qdrant
        try:
            res = await client.get(f"http://{settings.qdrant_host}:{settings.qdrant_port}/collections")
            results["qdrant"] = res.status_code == 200
        except:
            pass

        # Check Ollama
        try:
            res = await client.get(f"{settings.ollama_host}/api/tags")
            results["ollama"] = res.status_code == 200
        except:
            pass

    return JSONResponse(results)


async def dashboard(request: Request) -> FileResponse:
    """GET / - serve dashboard"""
    dashboard_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "dashboard",
        "index.html"
    )
    return FileResponse(dashboard_path)


async def add_project(request: Request) -> JSONResponse:
    """
    POST /api/projects
    Body: {
        "name": "project-name",
        "path": "/path/to/project",
        "description": "...",
        "status": "active|archived|planned",
        "tags": ["tag1"]
    }
    """
    try:
        data = await request.json()

        name = data.get("name", "").strip().lower()
        description = data.get("description", "").strip()

        if not name or not description:
            return JSONResponse({"error": "name and description are required"}, status_code=400)

        path = data.get("path")
        status = data.get("status", "active")
        tags = data.get("tags", [])
        metadata = data.get("metadata", {})

        project_id = f"p-{name}"

        # Check if exists
        existing = await qdrant.get_by_field(collection="projects", field="name", value=name)
        if existing:
            return JSONResponse({"error": f"Project '{name}' already exists"}, status_code=409)

        text_for_embedding = f"{name}\n{description}"
        embedding = await get_embeddings(text_for_embedding)

        payload = {
            "id": project_id,
            "name": name,
            "path": path,
            "description": description,
            "status": status,
            "tags": tags if isinstance(tags, list) else [t.strip() for t in tags.split(",")],
            "metadata": metadata,
            "created_at": datetime.utcnow().isoformat(),
            "updated_at": datetime.utcnow().isoformat()
        }

        await qdrant.upsert(collection="projects", id=project_id, vector=embedding, payload=payload)

        return JSONResponse({"success": True, "id": project_id, "name": name})

    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


async def list_projects(request: Request) -> JSONResponse:
    """
    GET /api/projects
    Query params:
        q: search query
        limit: max results
        status: filter by status
    """
    try:
        query = request.query_params.get("q", "")
        limit = int(request.query_params.get("limit", "20"))
        status_param = request.query_params.get("status", "")

        filters = {}
        if status_param:
            filters["status"] = status_param

        if query:
            embedding = await get_embeddings(query)
            results = await qdrant.search(
                collection="projects",
                vector=embedding,
                limit=limit,
                filters=filters if filters else None
            )
        else:
            results, _ = await qdrant.list_all(
                collection="projects",
                limit=limit,
                filters=filters if filters else None
            )

        return JSONResponse({"results": results, "count": len(results)})

    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


async def add_private(request: Request) -> JSONResponse:
    """
    POST /api/private
    Body: {
        "title": "...",
        "content": "...",
        "private_type": "note|context|preference|secret_ref",
        "tags": ["tag1"]
    }
    """
    try:
        data = await request.json()

        title = data.get("title", "").strip()
        content = data.get("content", "").strip()

        if not title or not content:
            return JSONResponse({"error": "title and content are required"}, status_code=400)

        private_type = data.get("private_type", "note")
        tags = data.get("tags", [])
        metadata = data.get("metadata", {})

        content_hash = hashlib.sha256(f"{title}{content}".encode()).hexdigest()[:12]
        entry_id = f"priv-{content_hash}"

        text_for_embedding = f"{title}\n\n{content}"
        embedding = await get_embeddings(text_for_embedding)

        payload = {
            "id": entry_id,
            "title": title,
            "content": content,
            "private_type": private_type,
            "tags": tags if isinstance(tags, list) else [t.strip() for t in tags.split(",")],
            "metadata": metadata,
            "created_at": datetime.utcnow().isoformat(),
            "updated_at": datetime.utcnow().isoformat()
        }

        await qdrant.upsert(collection="private", id=entry_id, vector=embedding, payload=payload)

        return JSONResponse({"success": True, "id": entry_id, "title": title})

    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


async def list_private(request: Request) -> JSONResponse:
    """
    GET /api/private
    Query params:
        q: search query
        limit: max results
        private_type: filter by type
    """
    try:
        query = request.query_params.get("q", "")
        limit = int(request.query_params.get("limit", "20"))
        type_param = request.query_params.get("private_type", "")

        filters = {}
        if type_param:
            filters["private_type"] = type_param

        if query:
            embedding = await get_embeddings(query)
            results = await qdrant.search(
                collection="private",
                vector=embedding,
                limit=limit,
                filters=filters if filters else None
            )
        else:
            results, _ = await qdrant.list_all(
                collection="private",
                limit=limit,
                filters=filters if filters else None
            )

        return JSONResponse({"results": results, "count": len(results)})

    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


async def graph_data(request: Request) -> JSONResponse:
    """GET /api/graph - graph data for tag relationships visualization"""
    try:
        knowledge_items, _ = await qdrant.list_all(collection="knowledge", limit=1000)
        skills_items, _ = await qdrant.list_all(collection="skills", limit=1000)

        nodes = []
        tag_to_items = {}  # tag -> [item_ids]

        # Process knowledge entries
        for item in knowledge_items:
            node_id = item.get("id", "")
            nodes.append({
                "id": node_id,
                "label": (item.get("title") or "")[:40],
                "type": "knowledge",
                "knowledge_type": item.get("knowledge_type", "note"),
                "tags": item.get("tags", []),
                "title": item.get("title", "")
            })
            for tag in item.get("tags", []):
                tag_to_items.setdefault(tag, []).append(node_id)

        # Process skills
        for item in skills_items:
            node_id = item.get("id", "")
            nodes.append({
                "id": node_id,
                "label": item.get("name", ""),
                "type": "skill",
                "tags": item.get("tags", []),
                "description": item.get("description", "")
            })
            for tag in item.get("tags", []):
                tag_to_items.setdefault(tag, []).append(node_id)

        # Build edges based on shared tags
        edge_map = {}
        for tag, ids in tag_to_items.items():
            if len(ids) < 2:
                continue
            for i, id1 in enumerate(ids):
                for id2 in ids[i + 1:]:
                    key = tuple(sorted([id1, id2]))
                    if key not in edge_map:
                        edge_map[key] = {"from": key[0], "to": key[1], "tags": [tag]}
                    else:
                        edge_map[key]["tags"].append(tag)

        edges = list(edge_map.values())

        return JSONResponse({
            "nodes": nodes,
            "edges": edges,
            "tag_stats": {tag: len(ids) for tag, ids in tag_to_items.items()}
        })

    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


# Routes
routes = [
    Route("/", dashboard, methods=["GET"]),
    Route("/health", health, methods=["GET"]),
    Route("/api/stats", stats, methods=["GET"]),
    Route("/api/sessions", sessions, methods=["GET"]),
    Route("/api/status", status, methods=["GET"]),
    Route("/api/graph", graph_data, methods=["GET"]),
    Route("/api/knowledge", add_knowledge, methods=["POST"]),
    Route("/api/knowledge", list_knowledge, methods=["GET"]),
    Route("/api/skills", add_skill, methods=["POST"]),
    Route("/api/skills", list_skills, methods=["GET"]),
    Route("/api/projects", add_project, methods=["POST"]),
    Route("/api/projects", list_projects, methods=["GET"]),
    Route("/api/private", add_private, methods=["POST"]),
    Route("/api/private", list_private, methods=["GET"]),
]

# CORS middleware for n8n
middleware = [
    Middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
    )
]

app = Starlette(routes=routes, middleware=middleware)


def main():
    port = int(os.getenv("REST_API_PORT", "8766"))
    host = os.getenv("REST_API_HOST", "0.0.0.0")

    print(f"Starting Knowledge REST API on {host}:{port}")
    print(f"  Qdrant: {settings.qdrant_host}:{settings.qdrant_port}")
    print(f"  Ollama: {settings.ollama_host}")
    print(f"")
    print(f"Dashboard: http://{host}:{port}/")
    print(f"")
    print(f"API Endpoints:")
    print(f"  POST /api/knowledge - add knowledge")
    print(f"  GET  /api/knowledge?q=search - search/list knowledge")
    print(f"  POST /api/skills - add skill")
    print(f"  GET  /api/skills - list skills")
    print(f"  POST /api/projects - add project")
    print(f"  GET  /api/projects - list projects")
    print(f"  POST /api/private - add private entry")
    print(f"  GET  /api/private - list private entries")

    uvicorn.run(app, host=host, port=port)


if __name__ == "__main__":
    main()
