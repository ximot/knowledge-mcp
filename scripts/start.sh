#!/bin/bash
# Knowledge MCP Server startup script

cd /home/ximot/knowledge-mcp
source .venv/bin/activate

# Configuration via environment variables (with sensible defaults)
export QDRANT_HOST=${QDRANT_HOST:-localhost}
export QDRANT_PORT=${QDRANT_PORT:-6333}
export OLLAMA_HOST=${OLLAMA_HOST:-http://localhost:11434}
export EMBEDDING_MODEL=${EMBEDDING_MODEL:-nomic-embed-text}
export VECTOR_SIZE=${VECTOR_SIZE:-768}
export MCP_PORT=${MCP_PORT:-8765}

exec python knowledge_mcp/http_server.py
