#!/bin/bash

# clean-ci-docker.sh - Clean up CI Docker resources

echo "🧹 Cleaning up CI Docker resources..."

# Stop and remove containers
docker-compose -f docker-compose.ci.yml down

# Remove volumes (this will delete test data)
echo "Removing Docker volumes (test data will be lost)..."
docker-compose -f docker-compose.ci.yml down -v

# Remove the CI image
echo "Removing CI Docker image..."
docker rmi memg-core_ci-runner 2>/dev/null || true
docker rmi memg-core_ci-dev 2>/dev/null || true

# Clean up dangling images
echo "Cleaning up dangling images..."
docker image prune -f

echo "✅ CI Docker cleanup completed!"
echo ""
echo "To rebuild: ./run-ci-local.sh"
