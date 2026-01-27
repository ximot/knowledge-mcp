# ---- Builder stage ----
FROM python:3.13-slim AS builder

WORKDIR /build

COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

# ---- Runtime stage ----
FROM python:3.13-slim

LABEL org.opencontainers.image.title="knowledge-mcp" \
      org.opencontainers.image.description="Self-hosted RAG knowledge base for AI coding assistants via MCP" \
      org.opencontainers.image.version="0.1.0" \
      org.opencontainers.image.source="https://github.com/ximot/knowledge-mcp"

WORKDIR /app

# Copy installed dependencies from builder
COPY --from=builder /install /usr/local

# Copy source code
COPY knowledge_mcp/ ./knowledge_mcp/

# Create non-root user
RUN useradd -m -u 1000 mcp && chown -R mcp:mcp /app
USER mcp

EXPOSE 8765

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8765/health')" || exit 1

# Default: HTTP server mode for Docker
CMD ["python", "knowledge_mcp/http_server.py"]
