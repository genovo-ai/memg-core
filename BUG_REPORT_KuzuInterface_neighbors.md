# 🐛 Bug Report: KuzuInterface.neighbors() Invalid Cypher Query Generation

## **Status:** ❌ **CONFIRMED BUG** - High Severity

**Reporter:** System Analysis
**Date:** 2024-12-19
**Component:** `memg_core.core.interfaces.kuzu.KuzuInterface.neighbors()`
**Severity:** HIGH - Breaks core relationship querying functionality

---

## **Problem Statement**

The `KuzuInterface.neighbors()` method generates invalid Cypher queries when a UUID is incorrectly passed as the `node_label` parameter instead of the expected node type ("Memory", "bug", etc.).

### **Invalid Query Generated:**
```cypher
MATCH (a:867ee953-be1a-43a3-915e-ed199c29f0eb {id: $id})-[r]-(n:Memory)
```

### **Expected Query:**
```cypher
MATCH (a:Memory {id: $id})-[r]-(n:Memory)
-- OR for specific memory types:
MATCH (a:bug {id: $id})-[r]-(n:Memory)
```

---

## **Root Cause Analysis**

### **Issue Location:**
- **File:** `src/memg_core/core/interfaces/kuzu.py`
- **Method:** `KuzuInterface.neighbors()`
- **Lines:** 235-239 (Cypher pattern generation)

### **Code Analysis:**
```python
def neighbors(self, node_label: str, node_id: str, ...):
    # Pattern generation uses node_label directly in Cypher
    if direction == "out":
        pattern = f"(a:{node_label} {{id: $id}})-[r{rel_part}]->(n{neighbor})"
    elif direction == "in":
        pattern = f"(a:{node_label} {{id: $id}})<-[r{rel_part}]-(n{neighbor})"
    else:
        pattern = f"(a:{node_label} {{id: $id}})-[r{rel_part}]-(n{neighbor})"
```

### **Problem:**
- **Parameter Confusion:** UUID being passed as `node_label` instead of `node_id`
- **No Validation:** Method doesn't validate that `node_label` is a valid node type
- **External Caller Error:** MCP layer or other callers incorrectly passing parameters

---

## **Impact Assessment**

### **Severity: HIGH**
- ❌ **Complete failure** of relationship querying when bug occurs
- ❌ **Silent failures** - invalid Cypher queries return empty results
- ❌ **Breaks MCP integration** - relationship-based searches fail
- ❌ **Data integrity concerns** - relationships become inaccessible

### **Affected Components:**
- MCP relationship querying tools
- Graph-based search functionality
- Neighbor expansion in search results
- Any external API calls using relationship queries

---

## **Reproduction Steps**

### **Minimal Reproduction:**
```python
from memg_core.core.interfaces.kuzu import KuzuInterface

kuzu = KuzuInterface()

# BUG: Passing UUID as node_label (should be "Memory" or "bug")
uuid_value = "867ee953-be1a-43a3-915e-ed199c29f0eb"
neighbors = kuzu.neighbors(
    node_label=uuid_value,  # ❌ WRONG - should be "Memory"
    node_id="some-other-uuid",
    direction="any",
    neighbor_label="Memory"
)
# Result: Invalid Cypher query, no results returned
```

### **Expected Behavior:**
```python
# CORRECT usage:
neighbors = kuzu.neighbors(
    node_label="Memory",     # ✅ Node type, not UUID
    node_id=uuid_value,      # ✅ UUID goes here
    direction="any",
    neighbor_label="Memory"
)
```

---

## **Proposed Solution**

### **1. Input Validation (Immediate Fix)**
Add validation in `KuzuInterface.neighbors()`:

```python
def neighbors(self, node_label: str, node_id: str, ...):
    # Validate node_label is not a UUID
    if self._is_uuid(node_label):
        raise ValueError(f"node_label must be a node type (e.g., 'Memory'), not UUID: {node_label}")

    # Validate node_id looks like a UUID
    if not self._is_uuid(node_id):
        raise ValueError(f"node_id must be a UUID, got: {node_id}")
```

### **2. Helper Method:**
```python
def _is_uuid(self, value: str) -> bool:
    """Check if string looks like a UUID"""
    import re
    uuid_pattern = r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$'
    return bool(re.match(uuid_pattern, value, re.IGNORECASE))
```

### **3. Parameter Documentation:**
```python
def neighbors(
    self,
    node_label: str,        # Node type: "Memory", "bug", "task", etc.
    node_id: str,          # UUID of the specific node
    rel_types: list[str] | None = None,
    direction: str = "any",
    limit: int = 10,
    neighbor_label: str | None = None,
) -> list[dict[str, Any]]:
    """Fetch neighbors of a node

    Args:
        node_label: Node type/table name (e.g., "Memory", "bug") - NOT a UUID
        node_id: UUID of the specific node to find neighbors for
        ...
    """
```

---

## **Test Cases**

### **Test 1: Valid Usage**
```python
def test_neighbors_valid_params():
    kuzu = KuzuInterface()
    result = kuzu.neighbors(
        node_label="Memory",
        node_id="550e8400-e29b-41d4-a716-446655440000",
        direction="any"
    )
    # Should work without errors
```

### **Test 2: Invalid Node Label (UUID)**
```python
def test_neighbors_invalid_node_label_uuid():
    kuzu = KuzuInterface()
    with pytest.raises(ValueError, match="node_label must be a node type"):
        kuzu.neighbors(
            node_label="550e8400-e29b-41d4-a716-446655440000",  # UUID - invalid
            node_id="another-uuid",
            direction="any"
        )
```

### **Test 3: Invalid Node ID (Non-UUID)**
```python
def test_neighbors_invalid_node_id():
    kuzu = KuzuInterface()
    with pytest.raises(ValueError, match="node_id must be a UUID"):
        kuzu.neighbors(
            node_label="Memory",
            node_id="not-a-uuid",  # Invalid UUID format
            direction="any"
        )
```

---

## **Investigation Needed**

### **Find the Source:**
1. **Check MCP layer** - Look for incorrect parameter passing in MCP tools
2. **Review external callers** - Find where UUID is being passed as node_label
3. **Test relationship queries** - Verify current behavior with real data

### **Search Commands:**
```bash
# Find all calls to neighbors() method
grep -r "\.neighbors(" src/ tests/

# Look for UUID variables being passed as first parameter
grep -r "neighbors.*[a-f0-9-]{36}" src/

# Check MCP server relationship handling
grep -r "node_label" mcp/
```

---

## **Priority & Next Steps**

### **Priority: HIGH**
This bug breaks core relationship functionality and should be fixed immediately.

### **Action Items:**
1. ✅ **Immediate:** Add input validation to prevent UUID as node_label
2. 🔄 **Investigation:** Find root cause - where is UUID being passed incorrectly?
3. 🔄 **Testing:** Add comprehensive test coverage for parameter validation
4. 🔄 **Documentation:** Update method documentation with clear parameter examples
5. 🔄 **Review:** Audit all callers of neighbors() method

### **Files to Modify:**
- `src/memg_core/core/interfaces/kuzu.py` - Add validation
- `tests/adapter/test_kuzu_interface.py` - Add test cases
- Any MCP files with incorrect parameter passing (TBD)

---

## **Notes**

- This bug likely affects the MCP integration mentioned by the user
- The core `_append_neighbors()` function in `retrieval.py` correctly passes "Memory" as node_label
- Issue is likely in external callers or MCP layer
- Fix should be backward-compatible with existing correct usage

**Status:** Ready for implementation ✅
