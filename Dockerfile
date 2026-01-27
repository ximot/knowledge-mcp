FROM python:3.12-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt uvicorn

# Copy source code
COPY knowledge_mcp/ ./knowledge_mcp/

# Create non-root user
RUN useradd -m -u 1000 mcp && chown -R mcp:mcp /app
USER mcp

# Default command (stdio mode)
# For HTTP mode use: python knowledge_mcp/http_server.py
CMD ["python", "-m", "knowledge_mcp.server"]
