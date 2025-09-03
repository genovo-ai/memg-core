FROM python:3.11-slim

# Accept build arguments (for validation only - files will be mounted at runtime)
ARG TARGET_PATH
ARG MEMG_YAML_SCHEMA
RUN test -n "$TARGET_PATH" || (echo "ERROR: TARGET_PATH build argument is required" && exit 1)
RUN test -n "$MEMG_YAML_SCHEMA" || (echo "ERROR: MEMG_YAML_SCHEMA build argument is required" && exit 1)

# Create non-root user for security
RUN groupadd -r memg && useradd -r -g memg -d /app -s /bin/bash memg

# Set working directory
WORKDIR /app

# Install system dependencies (temporarily for health checks)
RUN apt-get update && apt-get install -y \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy wheel file and requirements
# COPY memg_core-0.6.3.dev5-py3-none-any.whl /app/
COPY requirements_mcp.txt /app/requirements_mcp.txt

# Install MCP server dependencies (includes local memg-core wheel)
RUN pip install --no-cache-dir -r requirements_mcp.txt

# Return to app directory and create directories for persistent storage
WORKDIR /app
RUN mkdir -p /qdrant /kuzu /target

# Copy MCP server files from current directory
COPY mcp_server.py /app/
COPY yaml_docstring_helper.py /app/

# Note: YAML schema and .env files will be mounted at runtime in /target/

# Set proper ownership for non-root user
RUN chown -R memg:memg /app /qdrant /kuzu /target

# Keep curl for health checks, but clean up other packages
RUN apt-get autoremove -y && apt-get clean

# Switch to non-root user
USER memg

# Set default environment (can be overridden by docker-compose)
ENV MEMORY_SYSTEM_MCP_HOST=0.0.0.0
ENV MEMORY_SYSTEM_MCP_PORT=8888

# Expose the port from .env (default 8888)
EXPOSE 8888

# Health check using custom health endpoint
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD curl -f http://localhost:${MEMORY_SYSTEM_MCP_PORT}/health || exit 1

# Run the MCP server
CMD ["python", "mcp_server.py"]
