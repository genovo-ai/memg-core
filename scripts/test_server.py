#!/usr/bin/env python3
"""
Simple script to test that the FastAPI server can start up and serve requests.
"""

import sys
import time
import subprocess
import requests
from threading import Thread


def start_server():
    """Start the uvicorn server in a subprocess."""
    try:
        return subprocess.Popen(
            [
                sys.executable, "-m", "uvicorn",
                "memg_core.api.server:app",
                "--host", "127.0.0.1",
                "--port", "8000"
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
    except Exception as e:
        print(f"Failed to start server: {e}")
        return None


def test_endpoints():
    """Test basic endpoints after server starts."""
    base_url = "http://127.0.0.1:8000"

    # Wait for server to start
    max_retries = 30
    for i in range(max_retries):
        try:
            response = requests.get(f"{base_url}/health", timeout=2)
            if response.status_code == 200:
                print("✓ Server started successfully")
                break
        except requests.RequestException:
            time.sleep(0.5)
            if i == max_retries - 1:
                print("✗ Server failed to start within timeout")
                return False

    # Test health endpoint
    try:
        response = requests.get(f"{base_url}/health")
        if response.status_code == 200 and response.json().get("status") == "ok":
            print("✓ Health endpoint working")
        else:
            print(f"✗ Health endpoint failed: {response.status_code}")
            return False
    except Exception as e:
        print(f"✗ Health endpoint error: {e}")
        return False

    # Test search endpoint (expect 400 due to missing parameters)
    try:
        response = requests.post(f"{base_url}/v1/search", json={})
        if response.status_code == 422:  # Pydantic validation error for missing required fields
            print("✓ Search endpoint validation working")
        else:
            print(f"✗ Search endpoint unexpected response: {response.status_code}")
            return False
    except Exception as e:
        print(f"✗ Search endpoint error: {e}")
        return False

    # Test that routes are documented
    try:
        response = requests.get(f"{base_url}/docs")
        if response.status_code == 200:
            print("✓ API documentation available at /docs")
        else:
            print(f"✗ API docs failed: {response.status_code}")
    except Exception as e:
        print(f"✗ API docs error: {e}")

    return True


def main():
    """Main test routine."""
    print("Starting FastAPI server test...")

    # Start server
    server_process = start_server()
    if not server_process:
        return 1

    try:
        # Test endpoints
        success = test_endpoints()

        if success:
            print("\n✅ All tests passed! FastAPI server is working correctly.")
            print("Server available at: http://127.0.0.1:8000")
            print("API docs available at: http://127.0.0.1:8000/docs")
            return 0
        else:
            print("\n❌ Some tests failed.")
            return 1

    finally:
        # Clean up
        print("\nShutting down server...")
        server_process.terminate()
        server_process.wait(timeout=5)


if __name__ == "__main__":
    exit(main())
