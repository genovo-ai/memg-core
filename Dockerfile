# Multi-stage Dockerfile for CI/CD build and publishing
FROM python:3.11-slim AS builder

# Set working directory
WORKDIR /app

# Install build dependencies
RUN apt-get update && apt-get install -y \
    git \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Install Python build tools
RUN pip install --no-cache-dir --upgrade pip setuptools wheel build twine

# Copy source code
COPY src/ /app/src/
COPY pyproject.toml /app/
COPY README.md /app/
COPY LICENSE /app/

# Build the package
RUN python -m build

# Verify the package can be installed
RUN pip install dist/*.whl

# Test stage
FROM builder AS test

# Install test dependencies
RUN pip install --no-cache-dir pytest pytest-cov

# Copy tests
COPY tests/ /app/tests/

# Run tests
RUN python -m pytest tests/ -v

# Final stage for publishing
FROM python:3.11-slim AS publisher

# Install publishing tools
RUN pip install --no-cache-dir twine

# Copy built packages from builder stage
COPY --from=builder /app/dist/ /app/dist/

# Set working directory
WORKDIR /app

# Default command for publishing (requires PYPI_API_TOKEN)
CMD ["python", "-m", "twine", "upload", "--non-interactive", "dist/*"]
