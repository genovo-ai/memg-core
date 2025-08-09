FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies for graph databases
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    && rm -rf /var/lib/apt/lists/*

## Build and install package wheel for clean runtime
COPY pyproject.toml README.md ./
COPY src ./src/
RUN pip install --no-cache-dir build && \
    python -m build --wheel && \
    pip install --no-cache-dir dist/*.whl && \
    rm -rf src dist

# Set essential runtime environment variables
ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app/src

ENV MEMORY_SYSTEM_MCP_PORT=8787
ENV MEMORY_SYSTEM_MCP_HOST=0.0.0.0
ENV MEMORY_SYSTEM_LOG_LEVEL=INFO
ENV MEMG_VECTOR_DIMENSION=768
ENV EMBEDDING_DIMENSION_LEN=768
ENV GEMINI_MODEL=gemini-2.0-flash

ENV QDRANT_STORAGE_PATH=/qdrant
ENV KUZU_DB_PATH=/kuzu/memory_db

# SECURITY: API keys MUST be provided at runtime via env-file
ENV GOOGLE_API_KEY=""











# Expose default MCP port (can still map differently via compose)
EXPOSE 8787

# Run the installed package entrypoint
CMD ["python", "-m", "memory_system.mcp_server"]
