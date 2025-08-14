# Local CI with Docker

Run the complete GitHub Actions CI pipeline locally using Docker. This provides an exact replica of the Ubuntu 22.04 environment used in GitHub Actions.

## 🚀 Quick Start

```bash
# Run the complete CI pipeline locally
./run-ci-local.sh

# Interactive development shell for debugging
./dev-ci-shell.sh

# Start FastAPI server for local testing
./start-api-server.sh

# Test API endpoints
./test-api-endpoints.sh

# Clean up Docker resources
./clean-ci-docker.sh
```

## 📋 What It Does

The local CI pipeline runs the exact same steps as GitHub Actions:

1. **Security Scan** - Bandit security analysis
2. **Code Formatting** - Ruff format check
3. **Code Linting** - Ruff linting
4. **Type Checking** - MyPy static analysis
5. **Test Suite** - Complete pytest with coverage

## 🔧 Requirements

- Docker (via colima on Mac)
- Docker Compose

```bash
# Start colima if not running
colima start
```

## 📁 Files Created

- `Dockerfile.ci` - Exact replica of GitHub Actions Ubuntu environment
- `docker-compose.ci.yml` - Container orchestration
- `run-ci-local.sh` - Complete CI pipeline runner
- `dev-ci-shell.sh` - Interactive development environment
- `clean-ci-docker.sh` - Cleanup script

## 🛠️ Usage Examples

### Run Complete CI Pipeline
```bash
./run-ci-local.sh
```
This runs all checks and tests. If it passes, your code will pass GitHub CI!

### Start Local API Server
```bash
./start-api-server.sh
```
Starts FastAPI server at http://localhost:8000 with:
- API documentation: http://localhost:8000/docs
- Health check: http://localhost:8000/health
- All API endpoints for testing

### Test API Endpoints
```bash
./test-api-endpoints.sh
```
Automated testing of all API endpoints (requires server to be running)

### Debug Test Failures Interactively
```bash
./dev-ci-shell.sh
```
Then inside the container:
```bash
# Run specific tests
pytest tests/unit_temp/ -v

# Debug specific test
pytest tests/api/test_public_api.py::test_add_note_returns_memory_and_persists -vvs

# Check imports
python -c "from memg_core.api.public import add_note; print('✅ Import works')"

# Run linting
ruff check src/

# Run type checking
mypy src/ --ignore-missing-imports
```

### Quick Test Specific Areas
```bash
# Test only unit tests
docker-compose -f docker-compose.ci.yml run --rm ci-runner bash -c "pytest tests/unit_temp/ -v"

# Test only API
docker-compose -f docker-compose.ci.yml run --rm ci-runner bash -c "pytest tests/api/ -v"

# Run only linting
docker-compose -f docker-compose.ci.yml run --rm ci-runner bash -c "ruff check src/"
```

## 🎯 Benefits

1. **No More CI Surprises** - If it passes locally, it passes in CI
2. **Faster Debugging** - Debug test failures without pushing to GitHub
3. **Exact Environment** - Same Ubuntu, Python, and dependencies as CI
4. **Persistent Data** - Test databases persist between runs
5. **Live Mounting** - Edit code locally, test in container

## 🧹 Cleanup

```bash
# Remove containers and volumes
./clean-ci-docker.sh

# Or manually
docker-compose -f docker-compose.ci.yml down -v
docker image prune -f
```

## 🔍 Environment Details

The Docker environment matches GitHub Actions exactly:
- **OS**: Ubuntu 22.04
- **Python**: 3.11.x
- **Package Manager**: pip (latest)
- **Dependencies**: Installed from requirements.txt + dev dependencies
- **Environment Variables**: Same as CI (QDRANT_STORAGE_PATH, etc.)

## 🚨 Troubleshooting

### Docker Not Running
```bash
colima start
```

### Build Failures
```bash
# Clean everything and rebuild
./clean-ci-docker.sh
./run-ci-local.sh
```

### Permission Issues
```bash
# Ensure scripts are executable
chmod +x *.sh
```

### Storage Issues
```bash
# Clean up Docker space
docker system prune -a -f
```

This local CI setup eliminates the guess-work of whether your changes will pass GitHub Actions! 🎉
