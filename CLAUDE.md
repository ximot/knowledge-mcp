# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Knowledge MCP Server — a self-hosted RAG (Retrieval-Augmented Generation) knowledge base for AI coding assistants. Stores knowledge entries, skills (reusable prompts), project context, and private notes in a Qdrant vector database with embeddings from Ollama (nomic-embed-text).

Works with Claude Code, OpenCode, and any MCP-compatible client.

## Commands

```bash
# Install dependencies
pip install -r requirements.txt

# Run MCP server (stdio mode for Claude Code)
python -m knowledge_mcp

# Run HTTP server (remote access + dashboard)
python knowledge_mcp/http_server.py

# Import skills from SKILL.md files
python scripts/import_skills.py /path/to/skills/directory
python scripts/import_skills.py /path/to/single/SKILL.md

# Docker — full stack (MCP + Qdrant + Ollama)
docker compose up -d

# Docker — MCP server only (bring your own Qdrant + Ollama)
docker compose -f docker-compose.external.yml up -d

# Install as Python package (editable)
pip install -e .
```

## Architecture

```
knowledge_mcp/
├── __init__.py     # Package init, exports mcp, main, settings
├── __main__.py     # Entry point for: python -m knowledge_mcp
├── server.py       # Main MCP server — FastMCP tools for all CRUD operations
├── config.py       # Settings dataclass, loaded from environment variables
├── qdrant.py       # QdrantService — async client wrapper for vector operations
├── embeddings.py   # Ollama client for generating nomic-embed-text embeddings
└── http_server.py  # HTTP/SSE transport, /health endpoint, dashboard REST API

dashboard/
└── index.html      # Web dashboard (served at /dashboard by http_server.py)

scripts/
├── import_skills.py              # CLI tool for bulk SKILL.md import
├── start.sh                      # Shell startup helper
└── knowledge-mcp.service.example # Systemd unit template
```

**Data flow**: MCP tool call → Pydantic input validation → get_embeddings() → QdrantService → Qdrant DB

**Collections**: Four Qdrant collections with cosine similarity:
- `knowledge` — entries with id, title, content, knowledge_type, tags, source, metadata
- `skills` — prompts with id, name, description, prompt, tags, version, examples
- `projects` — project metadata with id, name, path, description, status, tags, metadata
- `private` — personal notes with id, title, content, private_type, tags, metadata

**IDs**:
- Knowledge: `k-{sha256(title+content)[:12]}`
- Skills: `s-{name}`
- Projects: `p-{name}`
- Private: `priv-{sha256(title+content)[:12]}`

## Environment Variables

```bash
QDRANT_HOST=localhost         # Qdrant server host
QDRANT_PORT=6333              # Qdrant REST port
QDRANT_API_KEY=               # Optional API key for Qdrant Cloud
QDRANT_HTTPS=false            # Use HTTPS for Qdrant

OLLAMA_HOST=http://localhost:11434  # Ollama server URL
EMBEDDING_MODEL=nomic-embed-text    # Embedding model name
VECTOR_SIZE=768                     # Embedding vector dimension

MCP_HOST=0.0.0.0              # HTTP server bind address
MCP_PORT=8765                 # HTTP server port
```

## HTTP Endpoints

- `/health` — Health check (Qdrant + Ollama connectivity)
- `/dashboard` — Web dashboard UI
- `/api/knowledge` — GET (list/search) / POST (add) knowledge entries
- `/api/skills` — GET (list/search) / POST (add) skills
- `/api/stats` — GET collection counts
- `/api/graph` — GET tag-based graph data for visualization
- `/mcp` — MCP protocol endpoint

## MCP Tools

**Knowledge**: `knowledge_search`, `knowledge_add`, `knowledge_get`, `knowledge_update`, `knowledge_delete`, `knowledge_list`

**Skills**: `skill_search`, `skill_get`, `skill_add`, `skill_update`, `skill_delete`, `skill_list`

**Projects**: `project_search`, `project_add`, `project_get`, `project_update`, `project_delete`, `project_list`

**Private**: `private_search`, `private_add`, `private_get`, `private_update`, `private_delete`, `private_list`

All tools use Pydantic models for input validation with `ConfigDict(str_strip_whitespace=True, extra='forbid')`.

## Key Implementation Details

- `QdrantService.ensure_collections()` auto-creates collections with payload indexes for `tags`, `knowledge_type`, `name`, `status`, `private_type` fields
- Embeddings truncate text to 8000 chars before sending to Ollama
- Search has default `score_threshold=0.3` for relevance filtering
- Response format supports both markdown (default) and JSON via `response_format` parameter
- Skill/Project names must match pattern `^[a-z0-9][a-z0-9-]*[a-z0-9]$|^[a-z0-9]$`
- Project status: `active`, `archived`, `planned`
- Private types: `note`, `context`, `preference`, `secret_ref`
