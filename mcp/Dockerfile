FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Build argument to control installation method
ARG USE_PYPI=false

# Install memg-core - either from PyPI or local source
RUN if [ "$USE_PYPI" = "true" ]; then \
        echo "📦 Installing memg-core from PyPI..." && \
        pip install --no-cache-dir memg-core; \
    fi

# Only copy local source files if NOT using PyPI
# We do this conditionally to avoid layer bloat when using PyPI
RUN if [ "$USE_PYPI" != "true" ]; then \
        echo "🔧 Preparing for local source installation..."; \
    fi

# Copy local source files (only needed for local builds)
COPY pyproject.toml README.md requirements.txt ./
COPY src/ ./src/

# Install from local source only if not using PyPI
RUN if [ "$USE_PYPI" != "true" ]; then \
        echo "📁 Installing from local source..." && \
        pip install --no-cache-dir -e .; \
    else \
        echo "📦 Using PyPI package, removing unnecessary source files..." && \
        rm -rf pyproject.toml README.md requirements.txt src/; \
    fi

# Copy and install MCP server dependencies
COPY mcp/requirements_mcp.txt /app/requirements_mcp.txt
RUN pip install --no-cache-dir -r requirements_mcp.txt

# Create directories for persistent storage and config
RUN mkdir -p /qdrant /kuzu /app/config

# Copy the MCP server file
COPY mcp/mcp_server.py /app/

# Copy the YAML schema specified in .env (build arg from compose)
ARG MEMG_YAML_SCHEMA
COPY ${MEMG_YAML_SCHEMA} /app/${MEMG_YAML_SCHEMA}

# Set environment variable for YAML schema
ENV MEMG_YAML_SCHEMA=${MEMG_YAML_SCHEMA}
ENV MEMORY_SYSTEM_MCP_HOST=0.0.0.0

EXPOSE 8787

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD curl -f http://localhost:${MEMORY_SYSTEM_MCP_PORT:-8787}/health || exit 1

# Run the MCP server
CMD ["python", "mcp_server.py"]
