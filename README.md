# Knowledge MCP Server

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Docker](https://img.shields.io/badge/Docker-ready-2496ED?logo=docker&logoColor=white)](docker-compose.yml)
[![Python 3.11+](https://img.shields.io/badge/Python-3.11+-3776AB?logo=python&logoColor=white)](https://python.org)

A self-hosted **RAG (Retrieval-Augmented Generation) knowledge base** for AI coding assistants. Store knowledge entries, reusable skills (prompts), project metadata, and private notes in a vector database. Access everything via [MCP (Model Context Protocol)](https://modelcontextprotocol.io/).

Works with **Claude Code**, **OpenCode**, and any MCP-compatible client. Powered by **Qdrant** + **Ollama** embeddings.

## Architecture

```
┌──────────────┐  ┌──────────────┐  ┌──────────────┐
│ Claude Code  │  │   OpenCode   │  │  MCP Client  │
└──────┬───────┘  └──────┬───────┘  └──────┬───────┘
       │                 │                 │
       └─────────────────┼─────────────────┘
                         │ MCP (stdio / HTTP+SSE)
                         ▼
              ┌─────────────────────┐
              │  Knowledge MCP      │
              │  Server (:8765)     │
              └──┬──────────────┬───┘
                 │              │
        ┌────────▼───┐  ┌──────▼──────┐
        │   Qdrant   │  │   Ollama    │
        │   (:6333)  │  │  (:11434)   │
        │ Vector DB  │  │ Embeddings  │
        └────────────┘  └─────────────┘
```

**Data flow:** MCP tool call → Pydantic validation → Ollama embeddings → Qdrant vector search/storage

**Collections:** Four Qdrant collections with cosine similarity:
- `knowledge` — documentation, how-tos, code snippets, references
- `skills` — reusable prompts and instructions
- `projects` — project metadata (name, path, description, status)
- `private` — personal notes, context, preferences

## Quick Start

### Docker (recommended)

**Prerequisites:** Docker and Docker Compose installed.

```bash
# 1. Clone the repository
git clone https://github.com/ximot/knowledge-mcp.git
cd knowledge-mcp

# 2. (Optional) Copy and edit config
cp .env.example .env

# 3. Start all services
docker compose up -d
```

### Local with uv (recommended for development)

**Prerequisites:** [uv](https://docs.astral.sh/uv/) installed, Qdrant and Ollama running.

```bash
# 1. Clone the repository
git clone https://github.com/ximot/knowledge-mcp.git
cd knowledge-mcp

# 2. Install dependencies
uv sync

# 3. Run the MCP server
uv run python -m knowledge_mcp
```

### Local with pip (alternative)

```bash
git clone https://github.com/ximot/knowledge-mcp.git
cd knowledge-mcp
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python -m knowledge_mcp
```

This starts three containers:
- **knowledge-mcp** — MCP server on port `8765`
- **qdrant** — vector database on port `6333`
- **ollama** — embedding model on port `11434` (auto-pulls `nomic-embed-text` on first start)

Verify everything is running:

```bash
curl http://localhost:8765/health
# {"status":"ok","qdrant":true,"ollama":true,"model":"nomic-embed-text"}
```

## Configuration Reference

All settings are configured via environment variables. Set them in a `.env` file or export directly.

| Variable | Default | Description |
|---|---|---|
| `QDRANT_HOST` | `localhost` | Qdrant server hostname |
| `QDRANT_PORT` | `6333` | Qdrant REST API port |
| `QDRANT_API_KEY` | _(empty)_ | API key for Qdrant Cloud or secured instances |
| `QDRANT_HTTPS` | `false` | Use HTTPS for Qdrant connection |
| `OLLAMA_HOST` | `http://localhost:11434` | Full Ollama server URL |
| `EMBEDDING_MODEL` | `nomic-embed-text` | Ollama embedding model name |
| `VECTOR_SIZE` | `768` | Embedding vector dimensions (must match model) |
| `MCP_HOST` | `0.0.0.0` | HTTP server bind address |
| `MCP_PORT` | `8765` | HTTP server port |

> When using `docker-compose.yml` (all-in-one), `QDRANT_HOST` and `OLLAMA_HOST` are automatically set to the container service names (`qdrant` and `http://ollama:11434`).

## MCP Tools Reference

The server exposes 24 tools across four collections. All tools support `markdown` (default) and `json` response formats.

### Knowledge

| Tool | Description |
|---|---|
| `knowledge_search` | Semantic search across knowledge entries. Filters: `knowledge_type`, `tags` |
| `knowledge_add` | Add a new entry (title, content, type, tags, source, metadata) |
| `knowledge_get` | Retrieve a single entry by ID |
| `knowledge_update` | Update fields of an existing entry (re-embeds on content change) |
| `knowledge_delete` | Permanently delete an entry by ID |
| `knowledge_list` | List entries with pagination and optional type/tag filters |

Knowledge types: `note`, `documentation`, `code_snippet`, `reference`, `howto`, `other`

### Skills

| Tool | Description |
|---|---|
| `skill_search` | Semantic search across skills |
| `skill_add` | Add a new skill (name, description, prompt, tags, version, examples) |
| `skill_get` | Retrieve a skill by exact name (includes full prompt) |
| `skill_update` | Update skill fields |
| `skill_delete` | Permanently delete a skill by name |
| `skill_list` | List all skills (names and descriptions, no prompts) |

Skill names must match: `^[a-z0-9][a-z0-9-]*[a-z0-9]$` (lowercase alphanumeric with hyphens)

### Projects

| Tool | Description |
|---|---|
| `project_search` | Semantic search for projects. Filters: `status`, `tags` |
| `project_add` | Add a project (name, path, description, status, tags, metadata) |
| `project_get` | Retrieve a project by exact name |
| `project_update` | Update project fields |
| `project_delete` | Permanently delete a project by name |
| `project_list` | List projects with pagination and status/tag filters |

Project statuses: `active`, `archived`, `planned`

### Private

| Tool | Description |
|---|---|
| `private_search` | Semantic search across private entries. Filters: `private_type`, `tags` |
| `private_add` | Add a private entry (title, content, type, tags, metadata) |
| `private_get` | Retrieve a private entry by ID |
| `private_update` | Update private entry fields |
| `private_delete` | Permanently delete a private entry by ID |
| `private_list` | List private entries with pagination and type/tag filters |

Private types: `note`, `context`, `preference`, `secret_ref`

## Usage with Claude Code

### Option 1: HTTP/SSE (recommended for Docker)

Add to `~/.claude/settings.json` or your project's `.claude/settings.json`:

```json
{
  "mcpServers": {
    "knowledge": {
      "url": "http://localhost:8765/mcp"
    }
  }
}
```

### Option 2: stdio (local Python)

Add to `~/.claude/settings.json`:

```json
{
  "mcpServers": {
    "knowledge": {
      "command": "python",
      "args": ["-m", "knowledge_mcp.server"],
      "cwd": "/path/to/knowledge-mcp",
      "env": {
        "QDRANT_HOST": "localhost",
        "OLLAMA_HOST": "http://localhost:11434"
      }
    }
  }
}
```

## Usage with Other Clients

### OpenCode

Add to your OpenCode MCP configuration:

```json
{
  "mcpServers": {
    "knowledge": {
      "url": "http://localhost:8765/mcp"
    }
  }
}
```

### Generic MCP Client

The server supports two transports:

- **stdio** — run `python -m knowledge_mcp.server` as a subprocess
- **HTTP (Streamable HTTP)** — connect to `http://<host>:8765/mcp`

The HTTP mode is stateless (`stateless_http=True`), so multiple clients can connect simultaneously.

## Advanced

### External Qdrant and Ollama

If you already have Qdrant and Ollama running (on your host, another server, or Qdrant Cloud), use the external compose file:

```bash
# Set connection details
export QDRANT_HOST=your-qdrant-host
export OLLAMA_HOST=http://your-ollama-host:11434

# Start only the MCP server
docker compose -f docker-compose.external.yml up -d
```

**Qdrant Cloud example:**

```env
QDRANT_HOST=abc123.us-east4-0.gcp.cloud.qdrant.io
QDRANT_PORT=6333
QDRANT_API_KEY=your-api-key-here
QDRANT_HTTPS=true
OLLAMA_HOST=http://localhost:11434
```

### Custom Embedding Models

You can use any Ollama-compatible embedding model. Change the model and update the vector size accordingly:

```env
EMBEDDING_MODEL=mxbai-embed-large
VECTOR_SIZE=1024
```

> Make sure to pull the model first: `ollama pull mxbai-embed-large`
>
> Changing the embedding model requires re-indexing all existing data since vector dimensions and semantics will differ.

### Importing Skills from SKILL.md Files

Bulk import skills from markdown files:

```bash
# Import all SKILL.md files from a directory (recursive)
python scripts/import_skills.py /path/to/skills/directory

# Import a single file
python scripts/import_skills.py /path/to/SKILL.md
```

SKILL.md format with optional YAML frontmatter:

```markdown
---
name: code-reviewer
description: Expert code reviewer for quality analysis
tags: [coding, review]
---

You are an expert code reviewer. Analyze code for:
1. Logic errors
2. Security issues
3. Performance problems
...
```

### Health Check

The HTTP server exposes a `/health` endpoint that verifies connectivity to both Qdrant and Ollama:

```bash
curl http://localhost:8765/health
```

```json
{
  "status": "ok",
  "qdrant": true,
  "ollama": true,
  "model": "nomic-embed-text"
}
```

Status is `"ok"` when both backends are reachable, `"degraded"` otherwise (returns HTTP 503).

## Development

### Local Setup (uv — recommended)

```bash
# Clone the repository
git clone https://github.com/ximot/knowledge-mcp.git
cd knowledge-mcp

# Install all dependencies (including dev tools: ruff, mypy)
uv sync --extra dev

# Start Qdrant (if not running)
docker run -d --name qdrant -p 6333:6333 qdrant/qdrant

# Ensure Ollama has the embedding model
ollama pull nomic-embed-text

# Run in stdio mode
uv run python -m knowledge_mcp.server

# Run in HTTP mode
uv run python knowledge_mcp/http_server.py

# Lint and format
uv run ruff check --fix .
uv run ruff format .

# Run tests
uv run pytest
```

### Local Setup (pip — alternative)

```bash
git clone https://github.com/ximot/knowledge-mcp.git
cd knowledge-mcp
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

python -m knowledge_mcp.server
```

### Project Structure

```
knowledge-mcp/
├── knowledge_mcp/
│   ├── __init__.py
│   ├── __main__.py        # python -m knowledge_mcp entry point
│   ├── server.py          # MCP server — all 24 tools
│   ├── config.py          # Settings from environment variables
│   ├── qdrant.py          # Qdrant async client wrapper
│   ├── embeddings.py      # Ollama embedding client
│   └── http_server.py     # HTTP/SSE transport + /health endpoint
├── scripts/
│   ├── import_skills.py   # Bulk SKILL.md importer
│   └── start.sh           # Shell startup script
├── examples/                   # Sample SKILL.md files and config snippets
├── docker-compose.yml          # All-in-one (MCP + Qdrant + Ollama)
├── docker-compose.external.yml # BYO backend (MCP server only)
├── Dockerfile
├── .env.example
├── requirements.txt
├── LICENSE
├── CLAUDE.md
└── README.md
```

## Contributing

Contributions are welcome. Please:

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/my-feature`)
3. Make your changes
4. Test with `docker compose up` to verify the full stack works
5. Submit a pull request

## License

[MIT](LICENSE)
