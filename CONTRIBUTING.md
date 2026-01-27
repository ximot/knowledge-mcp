# Contributing to knowledge-mcp

Thank you for your interest in contributing! This document provides guidelines for contributing to the project.

## Getting Started

1. Fork the repository
2. Clone your fork:
   ```bash
   git clone https://github.com/<your-username>/knowledge-mcp.git
   cd knowledge-mcp
   ```
3. Create a virtual environment and install dependencies:
   ```bash
   python -m venv .venv
   source .venv/bin/activate
   pip install -r requirements.txt
   ```
4. Make sure Qdrant and Ollama are running (see README.md for Docker setup).

## Development Setup

### Running locally

```bash
# MCP server (stdio mode for Claude Code)
python -m knowledge_mcp

# HTTP server (remote access + dashboard)
python knowledge_mcp/http_server.py
```

### Running with Docker

```bash
docker compose up -d
```

The dashboard is available at `http://localhost:8765/dashboard`.

## Making Changes

1. Create a feature branch from `main`:
   ```bash
   git checkout -b feature/my-feature
   ```
2. Make your changes.
3. Test locally — ensure the MCP server starts and the dashboard loads.
4. Commit with a clear message describing the change.
5. Push and open a pull request.

## Code Style

- Python 3.11+ with type hints
- Use `async/await` for I/O operations
- Follow existing patterns in the codebase (Pydantic models, QdrantService methods)
- Keep functions focused and small
- Use English for all code, comments, and documentation

## Project Structure

```
knowledge_mcp/      # Python package (MCP server, config, Qdrant client, embeddings)
dashboard/          # Static web dashboard (single HTML file)
scripts/            # Helper scripts (import_skills.py, start.sh)
```

See `CLAUDE.md` for detailed architecture and implementation notes.

## Reporting Issues

- Use GitHub Issues for bug reports and feature requests
- Include steps to reproduce for bugs
- Include your environment (Python version, OS, Docker version if applicable)

## License

By contributing, you agree that your contributions will be licensed under the MIT License.
