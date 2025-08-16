# Files to Move to _stash/ for Open Source Release

This report identifies files that should be moved to `_stash/` before publishing MEMG Core as an open source project. These files contain internal development artifacts, temporary files, or sensitive information that should not be included in the public repository.

Files have been categorized into:
- **Safe to Remove**: Low risk; can be moved without issues or mitigations.
- **Needs Adjustment**: Medium risk; can be moved but requires updates (e.g., to README.md or other docs) to avoid breakage.
- **Risky to Remove**: High risk; reconsider moving these, as they provide user-facing value or are referenced in docs.

These categories exclude files we're sure to keep (listed at the end).

## Safe to Remove (Low Risk)

These files are purely internal dev artifacts with no user-facing impact. Moving them cleans up the repo without breakage.

### Shell Scripts (Development/CI Tools)
- `start_server.sh` - Internal development server startup script
- `start-api-fast.sh` - Internal API server startup script  
- `start-api-server.sh` - Internal API server startup script
- `setup-dev.sh` - Internal development environment setup script
- `test-api-endpoints.sh` - Internal API testing script
- `test-mcp-server.sh` - Internal MCP server testing script
- `run-ci-docker.sh` - Internal CI Docker runner script
- `run-ci-fast.sh` - Internal fast CI runner script
- `run-ci-local.sh` - Internal local CI runner script
- `dev-ci-fast.sh` - Internal development CI script
- `dev-ci-shell.sh` - Internal development shell script
- `clean-ci-docker.sh` - Internal Docker cleanup script
- `build.sh` - Internal build script
- `ci_guardrails.sh` - Internal CI guardrails script

### Development Documentation
- `TASKS.md` - Internal task backlog and development roadmap (contains sensitive project planning)
- `test_issues_summary.txt` - Internal test failure analysis and debugging notes (contains sensitive debugging information)
- `CI-DOCKER-README.md` - Internal CI/Docker setup documentation (development-specific)
- `.pre-commit-setup.md` - Internal pre-commit setup guide (development-specific)

### Development Configuration
- `bandit.yaml` - Security scanning configuration (development-specific)
- `.pylintrc` - Pylint configuration (development-specific)
- `.pre-commit-config.yaml` - Pre-commit hooks configuration (development-specific)

### Docker Files (Development/CI)
- `Dockerfile.ci` - Internal CI Dockerfile
- `Dockerfile.ci-fast` - Internal fast CI Dockerfile
- `docker-compose.ci.yml` - Internal CI Docker Compose configuration
- `docker-compose.fast.yml` - Internal fast Docker Compose configuration

### Development Scripts
- `concat_docs.py` - Internal documentation concatenation script

### Temporary Data
- `temp_data/` - Temporary data directory (entire folder)

### Scripts Directory - Development/Testing Scripts
- `scripts/test_server.py` - Internal test server script
- `scripts/fastai_example.py` - Internal FastAI example (development-specific)

- `scripts/README.md` - Internal scripts documentation

### MCP Directory
- `mcp/` - Entire directory (contains internal MCP server implementation)
  - `mcp_server.py` - Internal MCP server implementation
  - `Dockerfile.mcp` - Internal MCP Dockerfile
  - `docker-compose.yml` - Internal MCP Docker Compose
  - `README.md` - Internal MCP documentation

## Needs Adjustment (Medium Risk)

These files can be moved, but adjustments (e.g., updating README.md references or adding summaries) are needed to mitigate usability issues or doc breakage.

### Examples Directory
- `examples/add_and_search.py` - Internal example script (development-specific). **Adjustment Needed**: Expand inline code examples in README.md to cover this script's functionality, as it's helpful for beginners.

## Risky to Remove (High Risk)

These files provide user-facing value (e.g., referenced in README.md or essential reference material). Moving them could break docs or reduce usability—reconsider or merge content elsewhere.

### Scripts Directory - Evaluation Scripts
- `scripts/evaluate_memg.py` - Internal evaluation script (development-specific)
- `scripts/generate_synthetic_dataset.py` - Internal synthetic data generation (development-specific). **Risk**: Directly referenced in README.md (Evaluation section); moving would break command examples.

### Configuration Directory
- `config/README.md` - Internal configuration documentation. **Risk**: Provides schema specs valuable for users extending YAML configs; referenced indirectly via config/ in README.md.

## Files to Keep in Repository

The following files should remain in the repository as they are essential for the open source release:

- `README.md` - Main project documentation
- `LICENSE` - MIT license
- `pyproject.toml` - Package configuration
- `requirements.txt` - Core dependencies
- `requirements-dev.txt` - Development dependencies
- `env.example` - Environment configuration example
- `src/` - Core library source code
- `tests/` - Test suite
- `config/core.minimal.yaml` - Core configuration file
- `.gitignore` - Git ignore rules
- `.dockerignore` - Docker ignore rules
- `.github/workflows/workflow.yml` - CI/CD workflow
- `yaml_based_ontology.md` - Technical documentation

## Next Steps

1. Move "Safe to Remove" files to `_stash/`.
2. For "Needs Adjustment" files, make required updates (e.g., to README.md) before moving.
3. For "Risky to Remove" files, decide whether to keep, merge content, or proceed with move (and handle breakage).
4. Remove empty directories from the main repository.
5. Update `.gitignore` to exclude `_stash/` from version control.
6. Test that the repository still builds and functions correctly.
7. Review and update any documentation that references moved files.
