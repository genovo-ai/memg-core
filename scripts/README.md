# Scripts

This folder contains development and testing scripts for memg-core.

## FastAPI Development Server

- **`fastai_example.py`**: Development/testing FastAPI server example
  - Run with: `python -m uvicorn scripts.fastai_example:app --reload`
  - Access at: http://127.0.0.1:8000
  - API docs at: http://127.0.0.1:8000/docs

- **`test_server.py`**: Automated test script for FastAPI server functionality
  - Run with: `python scripts/test_server.py`
- **`fastapi_server.py`**: Development FastAPI server (NOT part of core API)
  - Run with: `python scripts/fastapi_server.py`
  - Tests server startup, health endpoint, and basic API validation

## Production Server

For production use, the actual server implementation is at:

  - Includes all the same routes as the development example
