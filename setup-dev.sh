#!/bin/bash
# Development environment setup script for MEMG

set -e

echo "🔧 Setting up MEMG development environment..."

# Check if we're in a virtual environment
if [[ "$VIRTUAL_ENV" == "" ]]; then
    echo "⚠️  Warning: Not in a virtual environment. Consider activating one first."
    read -p "Continue anyway? (y/N): " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        echo "Exiting. Please activate a virtual environment and try again."
        exit 1
    fi
fi

# Install development dependencies
echo "📦 Installing development dependencies..."
pip install -e ".[dev]"

# Install pre-commit hooks
echo "🪝 Installing pre-commit hooks..."
pre-commit install

# Run pre-commit on all files to check setup
echo "🔍 Running pre-commit checks on all files..."
pre-commit run --all-files || echo "⚠️  Pre-commit found issues. Please fix them before committing."

echo "✅ Development environment setup complete!"
echo ""
echo "📋 Next steps:"
echo "1. Copy env.example to .env and configure your API keys"
echo "2. Run './start_server.sh' to start the MCP server"
echo "3. Run 'pytest' to run tests"
echo "4. Pre-commit hooks will now run automatically on every commit"
echo ""
echo "🚨 Important: CI now enforces linting! Fix issues before pushing."
