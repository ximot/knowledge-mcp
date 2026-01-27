# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Knowledge MCP Server - a RAG (Retrieval-Augmented Generation) server for Claude Code that stores knowledge entries and skills (reusable prompts) in Qdrant vector database with embeddings from Ollama (nomic-embed-text model).

## Commands

```bash
# Install dependencies
pip install -r requirements.txt

# Run MCP server (stdio mode for Claude Code)
python -m knowledge_mcp.server

# Run HTTP server for remote access
python knowledge_mcp/http_server.py

# Import skills from SKILL.md files
python import_skills.py /path/to/skills/directory
python import_skills.py /path/to/single/SKILL.md

# Docker deployment
docker-compose up -d
```

## Architecture

```
knowledge_mcp/
├── server.py      # Main MCP server - FastMCP tools for knowledge and skills CRUD
├── config.py      # Settings dataclass loading from environment variables
├── qdrant.py      # QdrantService - async client wrapper for vector operations
├── embeddings.py  # Ollama client for generating nomic-embed-text embeddings
└── http_server.py # HTTP/SSE transport wrapper using uvicorn for remote access
```

**Data flow**: MCP tool call → Pydantic input validation → get_embeddings() → QdrantService → Qdrant DB

**Collections**: Four Qdrant collections with cosine similarity:
- `knowledge` - entries with id, title, content, knowledge_type, tags, source, metadata
- `skills` - prompts with id, name, description, prompt, tags, version, examples
- `projects` - project metadata with id, name, path, description, status, tags, metadata
- `private` - personal notes with id, title, content, private_type, tags, metadata

**IDs**:
- Knowledge: `k-{sha256(title+content)[:12]}`
- Skills: `s-{name}`
- Projects: `p-{name}`
- Private: `priv-{sha256(title+content)[:12]}`

## Environment Variables

```bash
QDRANT_HOST=localhost    # Qdrant server host
QDRANT_PORT=6333         # Qdrant REST port
QDRANT_API_KEY=          # Optional auth
QDRANT_HTTPS=false       # Use HTTPS

OLLAMA_HOST=http://localhost:11434
EMBEDDING_MODEL=nomic-embed-text
VECTOR_SIZE=768          # nomic-embed-text dimension
```

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
