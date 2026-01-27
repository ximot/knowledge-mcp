# ---- Builder stage ----
FROM python:3.13-slim AS builder

COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

WORKDIR /build

COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-editable

# ---- Runtime stage ----
FROM python:3.13-slim

LABEL org.opencontainers.image.title="knowledge-mcp" \
      org.opencontainers.image.description="Self-hosted RAG knowledge base for AI coding assistants via MCP" \
      org.opencontainers.image.version="0.1.0" \
      org.opencontainers.image.source="https://github.com/ximot/knowledge-mcp"

WORKDIR /app

# Copy uv and virtual env from builder
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv
COPY --from=builder /build/.venv /app/.venv
ENV PATH="/app/.venv/bin:$PATH"

# Copy source code and dashboard
COPY knowledge_mcp/ ./knowledge_mcp/
COPY dashboard/ ./dashboard/

# Create non-root user
RUN useradd -m -u 1000 mcp && chown -R mcp:mcp /app
USER mcp

EXPOSE 8765

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8765/health')" || exit 1

# Default: HTTP server mode for Docker
CMD ["python", "knowledge_mcp/http_server.py"]
