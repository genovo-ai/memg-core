FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy local core package and install in editable mode
COPY pyproject.toml README.md requirements.txt /app/
COPY src/ /app/src/

# Install local memg-core from source (includes core deps from pyproject)
RUN pip install --no-cache-dir -e .

# Copy and install MCP server dependencies
COPY mcp/requirements_mcp.txt /app/requirements_mcp.txt
RUN pip install --no-cache-dir -r requirements_mcp.txt

# Create directories for persistent storage and config
RUN mkdir -p /qdrant /kuzu /app/config

# Copy the YAML schema and MCP server file
COPY config/core.minimal.yaml /app/config/
COPY mcp/mcp_server.py /app/

# Set environment variables for YAML schema
ENV MEMG_YAML_SCHEMA=/app/config/core.minimal.yaml
ENV MEMORY_SYSTEM_MCP_HOST=0.0.0.0

EXPOSE 8787

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD curl -f http://localhost:${MEMORY_SYSTEM_MCP_PORT:-8787}/health || exit 1

# Run the MCP server
CMD ["python", "mcp_server.py"]
