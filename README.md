# MEMG: The Radically Simplified Memory System for AI

**"True memory for AI - lightweight, generalist, AI-focused, open-source, and ethical"**

MEMG is an intelligent memory system for AI applications. It combines a vector database (Qdrant) for semantic search with a graph database (Kuzu) for relationship analysis, providing a powerful and flexible memory layer for AI agents and developers.

---

## ⚠️ Project Status: Radical Simplification in Progress

The MEMG project is currently undergoing a **radical simplification** to align with its core mission of being lightweight, efficient, and accessible.

While the current `main` branch contains a functional v0.4.0 implementation, it is overly complex (~8,000 lines of code) and does not meet our performance goals for low-resource devices.

**Our immediate and primary focus is a complete architectural refactoring with the following goals:**
- **~70% Codebase Reduction**: From 8,000+ lines to ~2,500 lines.
- **Unified Processing Pipeline**: A single, efficient processor to replace multiple redundant systems.
- **Simplified Storage**: A primary vector store (Qdrant) with an optional graph store (Kuzu).
- **Streamlined Models**: Simple, fast dataclasses instead of heavy, multi-layered Pydantic models.
- **Massive Performance Gains**: 70-80% faster startup and 30-50% faster processing.

This `README` reflects the vision and architecture of this new, simplified version.

---

## Architecture Overview (Target: v0.5.0)

The simplified MEMG architecture is designed for performance, clarity, and maintainability.

-   **Vector Database**: **Qdrant** for primary storage and fast semantic search.
-   **Graph Database**: **Kuzu** (optional) for storing and exploring relationships between memories.
-   **AI Model**: **Google Gemini** for entity extraction and content analysis.
-   **MCP Server**: **FastMCP**-based server exposing MCP tools for AI agents.
-   **Core Logic**: A single, streamlined processor for handling memory ingestion, analysis, and storage.

```
src/memory_system/
├── core.py                 # Core data models (Memory, Entity)
├── processor.py            # Single, unified processing pipeline
├── storage.py              # Simplified interface for Qdrant & Kuzu
├── ai_client.py            # Direct integration with Google Gemini
├── config.py               # Simplified environment-based configuration
├── mcp_server.py           # FastMCP server exposing MCP tools
└── utils.py                # Essential utilities
```

---

## Core Features for Developers

-   **Dual Storage, Simplified**: Get the power of semantic search and graph-based relationships without the complexity. Use vector search for speed, and opt-in to graph for deeper insights.
-   **Automated Knowledge Extraction**: Automatically extract key entities (e.g., `TECHNOLOGY`, `LIBRARY`, `ERROR`, `SOLUTION`) and their relationships from unstructured text.
-   **Developer-Centric Schema**: The default schema is optimized for technical knowledge management, helping you build powerful personal or team-based knowledge bases.
-   **User & Project Isolation**: Built-in data separation for multi-tenant applications.
-   **Local-First & Open Source**: Run it anywhere, from a Raspberry Pi to the cloud. Your data stays with you. No corporate lock-in.

---

## Getting Started

**🚀 Quick Start with MCP Server:**

```bash
# 1. Clone and setup
git clone https://github.com/your-repo/memg.git
cd memg

# 2. Add your Google API key
cp example.env .env
# Edit .env and add your GOOGLE_API_KEY

# 3. Start the server (builds and runs via Docker)
./start_server.sh
```

**✅ Verify the System is Running:**

```bash
curl http://localhost:8787/
```

You should see a JSON response indicating the system is healthy.

**🔄 Port Management for Development:**

The system uses port-based isolation for fast development cycles. Default is `8787` (dev-8787):

```bash
# To run on a different port (e.g., 8789 for dev-8789):
export MEMORY_SYSTEM_MCP_PORT=8789
./start_server.sh
```

Each port gets its own isolated storage at `~/.local/share/memory_system_PORT/`, allowing multiple development versions to run simultaneously without conflicts.

**🐳 Manual Docker (Alternative):**

```bash
# Set your port and start
export MEMORY_SYSTEM_MCP_PORT=8787
export BASE_MEMORY_PATH="$HOME/.local/share/memory_system"
mkdir -p "${BASE_MEMORY_PATH}_${MEMORY_SYSTEM_MCP_PORT}/"{qdrant,kuzu}
docker-compose -f dockerfiles/docker-compose.yml up -d
```

---

## Configuration

MEMG is configured via environment variables. See `example.env` for all available options.

**Required:**

-   `GOOGLE_API_KEY`: Your API key for Google Gemini.

**Common Optional:**

-   `MEMG_ENABLE_GRAPH`: Set to `true` or `false` to enable/disable the Kuzu graph database.
-   `KUZU_DB_PATH`: Filesystem path for the Kuzu database.
-   `QDRANT_STORAGE_PATH`: Filesystem path for the Qdrant database.

## Development

### 🚨 **IMPORTANT: Linting is Now Enforced**

As of the latest updates, **linting is strictly enforced in CI/CD**. The build will fail if code doesn't meet quality standards.

### Quick Setup

```bash
# 1. Clone and setup development environment
git clone <repo-url>
cd memg
./setup-dev.sh  # Installs deps and pre-commit hooks

# 2. Configure environment
cp env.example .env
# Edit .env with your API keys

# 3. Start development
./start_server.sh  # Start MCP server
pytest            # Run tests
```

### Pre-commit Hooks

Pre-commit hooks are **mandatory** and will automatically:
- Format code with `black` and `ruff`
- Check imports with `isort`  
- Run `pylint` with minimum score of 8.5/10
- Run `mypy` type checking
- Security scan with `bandit`

**The CI will fail if your code doesn't pass these checks.**

### Code Quality Standards

- **Pylint Score**: Minimum 8.5/10 (currently enforced)
- **Type Hints**: Required for all functions
- **Documentation**: Docstrings for public APIs
- **Security**: No high-severity bandit issues
- **Formatting**: Black + isort + ruff

## Mission & Philosophy

-   **Simplicity & Power**: Deliver powerful AI memory capabilities without the crushing complexity.
-   **Efficiency First**: Optimized for minimal resource usage. Every saved CPU cycle matters.
-   **Global Accessibility**: Built to be understood, used, and modified by a global community of developers.
-   **Ethical & Open**: Knowledge belongs to everyone. We build tools, not walls.
