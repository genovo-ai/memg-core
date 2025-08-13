#!/bin/bash
# CI guardrails to ensure core purity

echo "Running core purity checks..."

# Check that core does not depend on plugins
echo "Checking core does not import plugins..."
if grep -R "memg_core\.plugins" src/memg_core/core; then
    echo "❌ ERROR: Core imports from plugins!"
    exit 1
fi

# Check that core does not depend on showcase
echo "Checking core does not import showcase..."
if grep -R "memg_core\.showcase" src/memg_core/core; then
    echo "❌ ERROR: Core imports from showcase!"
    exit 1
fi

# Check retrieval pipeline does not read env
echo "Checking retrieval pipeline does not read env..."
if grep -n "os.getenv" src/memg_core/core/pipeline/retrieval.py; then
    echo "❌ ERROR: Retrieval pipeline reads environment variables!"
    exit 1
fi

# Check indexing/pipeline does not reference YAML
echo "Checking indexing does not reference YAML..."
if grep -n "yaml\|MEMG_YAML" src/memg_core/core/indexing.py src/memg_core/core/pipeline/indexer.py; then
    echo "❌ ERROR: Core indexing references YAML!"
    exit 1
fi

echo "✅ All core purity checks passed!"
