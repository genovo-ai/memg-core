# Scripts

This folder contains development and testing scripts for memg-core.

## FastAPI Development Server

- **`fastai_example.py`**: Development/testing FastAPI server example
  - Run with: `python -m uvicorn scripts.fastai_example:app --reload`
  - Access at: http://127.0.0.1:8000
  - API docs at: http://127.0.0.1:8000/docs

- **`test_server.py`**: Automated test script for FastAPI server functionality
  - Run with: `python scripts/test_server.py`
  - Tests server startup, health endpoint, and basic API validation

## Production Server

For production use, the actual server implementation is at:
- **`src/memg_core/api/server.py`**: Production FastAPI server
  - Run with: `python -m uvicorn memg_core.api.server:app`
  - Includes all the same routes as the development example
