#!/bin/bash
# Knowledge MCP Server startup script

cd /home/ximot/knowledge-mcp
source .venv/bin/activate

export QDRANT_HOST=192.168.1.9
export QDRANT_PORT=6333
export OLLAMA_HOST=http://192.168.1.9:11434
export EMBEDDING_MODEL=nomic-embed-text
export VECTOR_SIZE=768
export MCP_PORT=8765

exec python knowledge_mcp/http_server.py
