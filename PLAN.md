# PLAN.md — Open Source Release Plan

## Vision

**knowledge-mcp** — A self-hosted RAG knowledge base for AI coding assistants. Store knowledge, skills, project context, and private notes in a vector database. Access everything via MCP (Model Context Protocol).

Works with Claude Code, OpenCode, and any MCP-compatible client. Powered by Qdrant + Ollama embeddings.

---

## Phase 1: Code Cleanup (Priority: HIGH)

### 1.1 Remove local/private configuration
- [x] `knowledge_mcp/config.py` — Remove any hardcoded IPs (e.g., `192.168.1.9`), make everything env-driven
- [x] `knowledge_mcp/rest_api.py` — Removed (n8n integration = later)
- [x] `knowledge-rest-api.service` — Removed
- [x] `start-rest-api.sh` — Removed
- [x] `wrapper.log` — Gitignored, not tracked
- [x] `knowledge-mcp.service` — Renamed to `scripts/knowledge-mcp.service.example`
- [x] `.claude/` — Not tracked (gitignored)
- [x] `__pycache__/` dirs — Not tracked, gitignored
- [x] `.venv/` — Not tracked, gitignored

### 1.2 Translate Polish → English
- [x] `knowledge_mcp/server.py` — Translate all Polish comments/docstrings
- [x] `knowledge_mcp/config.py` — No Polish comments found
- [x] `knowledge_mcp/qdrant.py` — No Polish comments found
- [x] `knowledge_mcp/embeddings.py` — No Polish comments found
- [x] `knowledge_mcp/http_server.py` — No Polish comments found
- [x] `scripts/import_skills.py` — No Polish comments found
- [x] `scripts/start.sh` — Replaced hardcoded IPs with env vars

### 1.3 Code quality
- [x] Add type hints where missing — Existing code has good type hints
- [x] Ensure consistent error handling (return proper MCP errors) — All tools use try/except with descriptive messages
- [x] Review `import_skills.py` — clean up, make it a proper CLI tool — Already a proper CLI tool
- [x] Add `__main__.py` for `python -m knowledge_mcp` entry point

---

## Phase 2: Docker (Priority: HIGH)

### 2.1 Dockerfile
- [x] Multi-stage build: builder (install deps) → runtime (slim image)
- [x] Base: `python:3.13-slim`
- [x] Non-root user
- [x] Health check endpoint (`/health`)
- [x] Labels (version, description, repo URL)

### 2.2 docker-compose.yml — All-in-One
Full stack for quick start:
```yaml
services:
  knowledge-mcp:  # The MCP server (port 8765)
  qdrant:          # Vector DB (port 6333)
  ollama:          # Embeddings (port 11434)
```
- [x] Auto-pull `nomic-embed-text` model on first start (init container or entrypoint script)
- [x] Shared network
- [x] Named volumes for Qdrant data and Ollama models
- [x] Health checks for all services
- [x] `.env` file support

### 2.3 docker-compose.external.yml — BYO Backend
Minimal — just the MCP server:
```yaml
services:
  knowledge-mcp:  # Points to external Qdrant + Ollama via env vars
```
- [x] Document required env vars for external connections
- [x] Example for connecting to remote Qdrant Cloud

### 2.4 Health check endpoint
- [x] Add `/health` endpoint to `http_server.py`
- [x] Check Qdrant connectivity
- [x] Check Ollama connectivity + model availability
- [x] Return structured JSON: `{ "status": "ok", "qdrant": true, "ollama": true, "model": "nomic-embed-text" }`

---

## Phase 3: Documentation (Priority: HIGH)

### 3.1 README.md (English)
- [x] Project description + badges (license, Docker pulls, etc.)
- [x] Architecture diagram (ASCII or Mermaid)
- [x] **Quick Start** — `docker compose up` in 3 commands
- [x] **Configuration Reference** — all env vars with defaults
- [x] **MCP Tools Reference** — all 24 tools with descriptions
- [x] **Usage with Claude Code** — how to add to `~/.claude/mcp.json`
- [x] **Usage with other clients** — OpenCode, generic MCP
- [x] **Advanced** — external Qdrant, custom embedding models, importing skills
- [x] **Development** — local setup, running tests
- [x] **Contributing** section

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
- [x] Review existing `API.md` — update or merge into README
- [x] Document MCP tool schemas (inputs/outputs)

---

## Phase 4: Dashboard (Priority: MEDIUM)

### 4.1 Review current state
- [x] Audit `dashboard/` directory — what's there, does it work?
- [x] Identify dependencies and build process
- [x] Fix any hardcoded URLs/configs

### 4.2 Integration
- [x] Serve dashboard from MCP server (static files) or separate container
- [x] Add to docker-compose as optional service
- [x] Document how to access it

---

## Phase 5: Repository Setup (Priority: HIGH)

### 5.1 Git housekeeping
- [x] `.gitignore` — Python, Docker, IDE files, `.env`, `__pycache__`, `.venv`, logs
- [x] Remove tracked files that should be ignored (`.venv/`, `__pycache__/`, `wrapper.log`, `.claude/`)
- [ ] Clean git history if needed — old commits still contain a private LAN IP (`192.168.1.9`) in `scripts/start.sh` history; not a secret, low priority, left as-is

### 5.2 GitHub repo structure (done — matches target layout)
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
- [x] `LICENSE` — MIT
- [x] `CONTRIBUTING.md` — basic contribution guidelines
- [x] `pyproject.toml` — proper Python package metadata
- [x] `.github/workflows/ci.yml` — lint, typecheck, Docker build, GHCR publish on tag push

---

## Phase 6: Polish & Release (Priority: MEDIUM)

### 6.1 Testing
- [x] Verify all Python files compile (`py_compile` for each)
- [x] Verify docker-compose.yml and docker-compose.external.yml are valid YAML
- [x] Verify Dockerfile syntax (multi-stage build, labels, healthcheck)
- [x] Verify pyproject.toml is valid and has description + repo URLs
- [ ] **No automated test suite exists** — no `tests/` directory anywhere in the repo; CI only runs lint + typecheck. In progress, see Phase 7.
- [ ] Ensure `docker compose up` works from clean state (manual, needs live Qdrant/Ollama)
- [ ] Test MCP connection from Claude Code (manual)
- [ ] Test all 24 tools (CRUD for each collection) — being covered by automated tests, see Phase 7
- [ ] Test import_skills.py with sample SKILL.md files (manual)

### 6.2 Sample data
- [x] Add `examples/` directory with sample SKILL.md files for import
- [x] Add example MCP client config snippets

### 6.3 Release
- [x] Review all files for consistency
- [x] Verify .gitignore covers Python, Docker, IDE, .env, logs, etc.
- [x] Verify pyproject.toml has repo description and URLs
- [x] Final README review — Quick Start, project structure updated
- [x] Create GitHub repo: `ximot/knowledge-mcp`
- [x] Push clean code
- [x] Add repo description + topics (ai-tools, claude-code, knowledge-base, mcp, ollama, qdrant, rag, vector-database)
- [x] Create initial release tag (v0.1.0)
- [x] Publish Docker image to GHCR — automated in CI on tag push

---

## Phase 7: Post-v0.1.0 Hardening (Priority: HIGH) — status as of 2026-07-14

v0.1.0 shipped and Phases 1-6 above are effectively complete (this checklist was stale — verified against actual repo state on 2026-07-14). Real remaining work:

### 7.1 Automated tests
- [ ] Add `tests/` with pytest covering `config.py`, `qdrant.py`, `embeddings.py`, and Pydantic input validation in `server.py`
- [ ] Wire `pytest` into `.github/workflows/ci.yml`

### 7.2 Dashboard enhancements (open GitHub issues)
- [ ] #6 delete with confirmation (medium)
- [ ] #5 inline edit for entries (medium)
- [ ] #7 tag filtering from graph (medium)
- [ ] #8 responsive mobile layout (medium)
- [ ] #9 auto-refresh stats (medium)
- [ ] #10 import/export functionality (ambitious)
- [ ] #11 MCP playground / tool tester (ambitious)
- [ ] #12 usage analytics and charts (ambitious)

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
