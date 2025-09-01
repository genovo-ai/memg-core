# MEMG Core - Upcoming Features & Roadmap

This document outlines planned features, improvements, and their implementation priorities for the MEMG Core system.

---

## 🔴 **High Priority Features**

### 1. Memory Update Functionality ⭐ **CRITICAL**

**Problem**: No way to update existing memories without breaking relationships. Delete + Add creates new IDs, orphaning relationships.

**Solution**:
- Add `update_memory` MCP tool
- Use HRID to lookup existing UUID
- Perform upsert operation on same Qdrant point
- Preserve relationships by maintaining UUID consistency

**Implementation Strategy**:
```python
# Pseudo-code approach
def update_memory(hrid, new_payload):
    uuid = hrid_tracker.get_uuid(hrid)  # Existing mapping
    # Update Qdrant point with same UUID (upsert)
    # Update Kuzu node with same UUID
    # Relationships remain intact
```

**Benefits**:
- Preserves relationship integrity
- Enables memory evolution over time
- Critical for real-world usage scenarios

---

### 2. Enum Validation & Choice Surfacing ⭐ **HIGH**

**Problem**: Enum constraints not enforced; users don't know valid choices when updating memories.

**Solution**:
- Implement runtime enum validation in memory creation/updates
- Surface enum choices in MCP tool descriptions
- Provide validation errors with available choices

**Implementation Needs**:
- Schema parser to extract enum constraints
- Validation layer in memory operations
- Dynamic tool descriptions showing valid enum values
- Clear error messages: "Invalid status 'completed'. Valid choices: [backlog, todo, in_progress, in_review, done, cancelled]"

**Impact**: Data integrity + better UX

---

### 3. Relationship Deletion ⭐ **HIGH**

**Problem**: No way to remove relationships once created. Need to delete specific relationships without recreating entities.

**Solution**:
- Add `delete_relationship` MCP tool
- Use same parameters as `add_relationship` for consistency
- Target specific relationship tables for deletion

**Implementation**:
```python
def delete_relationship(from_hrid, to_hrid, relation_type, from_memory_type, to_memory_type):
    # Same lookup logic as add_relationship
    # Delete from specific Kuzu relationship table
```

**Benefits**: Complete relationship lifecycle management

---

## 🟡 **Medium Priority Features**

### 4. Memory Type Inference in Relationships ⭐ **MEDIUM**

**Problem**: `add_relationship` requires memory types when HRID format already indicates type ("DOCUMENT_AAA001" → "document").

**Solution**:
- Make memory types optional in relationship operations
- Infer types from HRID prefixes when not provided
- Keep explicit types for validation/safety when desired

**Implementation**:
```python
def infer_memory_type(hrid):
    prefix = hrid.split('_')[0].lower()
    return prefix  # "DOCUMENT_AAA001" → "document"
```

**Benefits**: Cleaner API, reduced verbosity

---

### 5. Direct Memory Retrieval (get_memory/get_memories) ⭐ **MEDIUM**

**Problem**: No way to retrieve specific memories by ID or filter by type without semantic search.

**Solution**: Add `get_memories` tool with multiple access patterns:
- By specific HRID: `get_memories(hrid="TASK_AAA001")`
- By type + filters: `get_memories(memory_type="task", filters={"status": "in_progress"})`
- By multiple HRIDs: `get_memories(hrids=["TASK_AAA001", "BUG_AAA000"])`

**Use Cases**:
- Explore specific memory details
- List all open tasks/bugs
- Check relationship endpoints
- Dashboard/stats functionality

**Benefits**: Complements semantic search with direct access patterns

---

### 6. Relationship Inheritance Decision ⭐ **MEDIUM**

**Problem**: Relationships don't inherit from parent entities. Need to decide inheritance strategy.

**Options**:
1. **No Inheritance** (current): Explicit relationship definitions only
2. **Full Inheritance**: Child entities inherit all parent relationships
3. **Optional Inheritance**: Schema flag to enable/disable per relationship

**Recommendation**: Optional inheritance with schema control:
```yaml
relations:
  memo:
    - name: memo_related
      predicate: RELATED_TO
      inherit: true  # Child entities get this relationship
```

**Benefits**: Flexibility without breaking existing schemas

---

## 🔵 **Lower Priority Features**

### 7. Access Control & User Scoping ⭐ **LOW**

**Problem**: Any user can edit any memory by changing user_id. Need access control.

**Solution**: Implement memory-level permissions:
- `owner`: Full CRUD access
- `collaborator`: Read + relationship creation
- `viewer`: Read-only access

**Implementation Complexity**: High - requires permission system, scope checking in all operations

**Future Consideration**: Important for multi-user environments but complex to implement correctly

---

### 8. Bulk Data Loading (ETL) ⭐ **LOW**

**Problem**: No way to bulk import predefined documents, datasets, or initial data.

**Solution Options**:
1. **MCP Bulk Import**: Extend MCP with batch operations
2. **HTTP Bulk Endpoint**: Direct database loading via HTTP API
3. **Offline Import**: CSV/JSON/JSONL import tools

**Considerations**:
- Database locking during bulk operations
- Relationship creation in bulk
- Validation at scale
- Progress reporting

**Recommended Approach**: Start with MCP batch operations, expand to offline tools as needed

---

## 📋 **Implementation Priority Order**

### **Phase 1: Core Functionality Completion**
1. Memory Update (`update_memory`)
2. Relationship Deletion (`delete_relationship`)
3. Enum Validation & Choice Surfacing

### **Phase 2: API Improvements**
4. Memory Type Inference in Relationships
5. Direct Memory Retrieval (`get_memories`)

### **Phase 3: Advanced Features**
6. Relationship Inheritance Strategy
7. Access Control System
8. Bulk Data Loading

---

## 🔍 **Technical Considerations**

### **Database Consistency**
- All update operations must maintain UUID consistency
- Relationship operations must handle orphaned references gracefully
- Bulk operations need transaction safety

### **API Design Principles**
- Backward compatibility for existing tools
- Optional parameters for enhanced usability
- Clear error messages with actionable guidance
- Consistent parameter patterns across tools

### **Performance Implications**
- HRID → UUID lookups add overhead but enable functionality
- Bulk operations need batching strategies
- Enum validation adds processing cost but improves data quality

---

## 🚀 **Quick Wins for Immediate Impact**

1. **Memory Update**: Solves critical workflow limitation
2. **Relationship Deletion**: Completes relationship lifecycle
3. **Enum Choice Surfacing**: Improves user experience immediately

These three features would significantly enhance the system's usability for real-world software development workflows.

---

*Last Updated: 2025-01-31*
*Priority Assessment: Based on user feedback and testing insights*
