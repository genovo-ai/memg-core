FROM python:3.11-slim

# Accept build arguments
ARG YAML_FILE
RUN test -n "$YAML_FILE" || (echo "ERROR: YAML_FILE build argument is required" && exit 1)

# Create non-root user for security
RUN groupadd -r memg && useradd -r -g memg -d /app -s /bin/bash memg

# Set working directory
WORKDIR /app

# Install system dependencies (temporarily for health checks)
RUN apt-get update && apt-get install -y \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy wheel file and requirements
COPY requirements_mcp.txt /app/requirements_mcp.txt
COPY memg_core-0.7.4.dev9-py3-none-any.whl /app/

# Install MCP server dependencies (includes local memg-core wheel)
RUN pip install --no-cache-dir -r requirements_mcp.txt

# Return to app directory and create directories for persistent storage
WORKDIR /app
RUN mkdir -p /app/databases/qdrant /app/databases/kuzu

# Copy MCP server files and YAML schema
COPY server.py /app/
COPY ${YAML_FILE} /app/schema.yaml

# Set proper ownership for non-root user
RUN chown -R memg:memg /app

# Keep curl for health checks, but clean up other packages
RUN apt-get autoremove -y && apt-get clean

# Switch to non-root user
USER memg

# Run the MCP server
CMD fastmcp run server.py:mcp_app --transport http --host 0.0.0.0 --port ${MEMORY_SYSTEM_MCP_PORT:-8778}
