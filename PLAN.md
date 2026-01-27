# PLAN.md — Open Source Release Plan

## Vision

**knowledge-mcp** — A self-hosted RAG knowledge base for AI coding assistants. Store knowledge, skills, project context, and private notes in a vector database. Access everything via MCP (Model Context Protocol).

Works with Claude Code, OpenCode, and any MCP-compatible client. Powered by Qdrant + Ollama embeddings.

---

## Phase 1: Code Cleanup (Priority: HIGH)

### 1.1 Remove local/private configuration
- [ ] `knowledge_mcp/config.py` — Remove any hardcoded IPs (e.g., `192.168.1.9`), make everything env-driven
- [ ] `knowledge-rest-wrapper.py` — Remove from main branch (n8n integration = later)
- [ ] `knowledge-rest-api.service` — Remove (related to wrapper)
- [ ] `start-rest-api.sh` — Remove (related to wrapper)
- [ ] `wrapper.log` — Remove (should be gitignored)
- [ ] `knowledge-mcp.service` — Keep as example, rename to `knowledge-mcp.service.example`
- [ ] `.claude/` — Remove from repo (local Claude Code settings)
- [ ] `__pycache__/` dirs — Remove, add to `.gitignore`
- [ ] `.venv/` — Remove from repo, add to `.gitignore`

### 1.2 Translate Polish → English
- [ ] `knowledge_mcp/server.py` — Translate all Polish comments/docstrings
- [ ] `knowledge_mcp/config.py` — Translate comments
- [ ] `knowledge_mcp/qdrant.py` — Translate comments
- [ ] `knowledge_mcp/embeddings.py` — Translate comments
- [ ] `knowledge_mcp/http_server.py` — Translate comments
- [ ] `import_skills.py` — Translate comments
- [ ] `start.sh` — Translate comments

### 1.3 Code quality
- [ ] Add type hints where missing
- [ ] Ensure consistent error handling (return proper MCP errors)
- [ ] Review `import_skills.py` — clean up, make it a proper CLI tool
- [ ] Add `__main__.py` for `python -m knowledge_mcp` entry point

---

## Phase 2: Docker (Priority: HIGH)

### 2.1 Dockerfile
- [ ] Multi-stage build: builder (install deps) → runtime (slim image)
- [ ] Base: `python:3.13-slim`
- [ ] Non-root user
- [ ] Health check endpoint (`/health`)
- [ ] Labels (version, description, repo URL)

### 2.2 docker-compose.yml — All-in-One
Full stack for quick start:
```yaml
services:
  knowledge-mcp:  # The MCP server (port 8765)
  qdrant:          # Vector DB (port 6333)
  ollama:          # Embeddings (port 11434)
```
- [ ] Auto-pull `nomic-embed-text` model on first start (init container or entrypoint script)
- [ ] Shared network
- [ ] Named volumes for Qdrant data and Ollama models
- [ ] Health checks for all services
- [ ] `.env` file support

### 2.3 docker-compose.external.yml — BYO Backend
Minimal — just the MCP server:
```yaml
services:
  knowledge-mcp:  # Points to external Qdrant + Ollama via env vars
```
- [ ] Document required env vars for external connections
- [ ] Example for connecting to remote Qdrant Cloud

### 2.4 Health check endpoint
- [ ] Add `/health` endpoint to `http_server.py`
- [ ] Check Qdrant connectivity
- [ ] Check Ollama connectivity + model availability
- [ ] Return structured JSON: `{ "status": "ok", "qdrant": true, "ollama": true, "model": "nomic-embed-text" }`

---

## Phase 3: Documentation (Priority: HIGH)

### 3.1 README.md (English)
- [ ] Project description + badges (license, Docker pulls, etc.)
- [ ] Architecture diagram (ASCII or Mermaid)
- [ ] **Quick Start** — `docker compose up` in 3 commands
- [ ] **Configuration Reference** — all env vars with defaults
- [ ] **MCP Tools Reference** — all 24 tools with descriptions
- [ ] **Usage with Claude Code** — how to add to `~/.claude/mcp.json`
- [ ] **Usage with other clients** — OpenCode, generic MCP
- [ ] **Advanced** — external Qdrant, custom embedding models, importing skills
- [ ] **Development** — local setup, running tests
- [ ] **Contributing** section

### 3.2 .env.example
```env
# Qdrant
QDRANT_HOST=qdrant
QDRANT_PORT=6333
# QDRANT_API_KEY=
# QDRANT_HTTPS=false

# Ollama
OLLAMA_HOST=http://ollama:11434
EMBEDDING_MODEL=nomic-embed-text
VECTOR_SIZE=768

# Server
MCP_HOST=0.0.0.0
MCP_PORT=8765
```

### 3.3 API.md
- [ ] Review existing `API.md` — update or merge into README
- [ ] Document MCP tool schemas (inputs/outputs)

---

## Phase 4: Dashboard (Priority: MEDIUM)

### 4.1 Review current state
- [ ] Audit `dashboard/` directory — what's there, does it work?
- [ ] Identify dependencies and build process
- [ ] Fix any hardcoded URLs/configs

### 4.2 Integration
- [ ] Serve dashboard from MCP server (static files) or separate container
- [ ] Add to docker-compose as optional service
- [ ] Document how to access it

---

## Phase 5: Repository Setup (Priority: HIGH)

### 5.1 Git housekeeping
- [ ] `.gitignore` — Python, Docker, IDE files, `.env`, `__pycache__`, `.venv`, logs
- [ ] Remove tracked files that should be ignored (`.venv/`, `__pycache__/`, `wrapper.log`, `.claude/`)
- [ ] Clean git history if needed (remove any secrets/IPs from history)

### 5.2 GitHub repo structure
```
knowledge-mcp/
├── knowledge_mcp/
│   ├── __init__.py
│   ├── __main__.py          # NEW: python -m knowledge_mcp
│   ├── server.py
│   ├── config.py
│   ├── qdrant.py
│   ├── embeddings.py
│   └── http_server.py
├── dashboard/                # Web UI
├── scripts/
│   ├── import_skills.py      # Moved from root
│   └── start.sh              # Moved from root
├── docker-compose.yml        # All-in-one
├── docker-compose.external.yml
├── Dockerfile
├── .env.example
├── .gitignore
├── LICENSE                   # MIT
├── README.md
├── CLAUDE.md                 # Updated for contributors
├── CONTRIBUTING.md           # NEW
├── requirements.txt
└── pyproject.toml            # NEW: proper Python packaging
```

### 5.3 Files to add
- [ ] `LICENSE` — MIT
- [ ] `CONTRIBUTING.md` — basic contribution guidelines
- [ ] `pyproject.toml` — proper Python package metadata
- [ ] `.github/workflows/ci.yml` — basic CI (lint, type check, Docker build test)

---

## Phase 6: Polish & Release (Priority: MEDIUM)

### 6.1 Testing
- [ ] Ensure `docker compose up` works from clean state
- [ ] Test MCP connection from Claude Code
- [ ] Test all 24 tools (CRUD for each collection)
- [ ] Test import_skills.py with sample SKILL.md files

### 6.2 Sample data
- [ ] Add `examples/` directory with sample SKILL.md files for import
- [ ] Add example MCP client config snippets

### 6.3 Release
- [ ] Create GitHub repo: `ximot/knowledge-mcp`
- [ ] Push clean code
- [ ] Add repo description + topics (mcp, rag, knowledge-base, qdrant, ollama, claude-code)
- [ ] Create initial release tag (v0.1.0)
- [ ] Optional: publish Docker image to GHCR

---

## Future (Post-Release)

- [ ] REST API wrapper for n8n integration
- [ ] Support for additional embedding models (OpenAI, local alternatives)
- [ ] Authentication/API keys for multi-user setups
- [ ] Backup/restore tools for Qdrant collections
- [ ] Web UI improvements (dashboard)
- [ ] PyPI package publication
- [ ] MCP Marketplace listing

---

## Execution Order

1. **Phase 1** (cleanup) + **Phase 5.1** (gitignore) — do first, foundation
2. **Phase 2** (Docker) — containerize everything
3. **Phase 3** (docs) — README, .env.example
4. **Phase 5.2-5.3** (repo structure, license, CI)
5. **Phase 4** (dashboard) — nice to have for v0.1
6. **Phase 6** (test, release)

Estimated effort: ~2-3 focused sessions with Claude Code / coding agent.
