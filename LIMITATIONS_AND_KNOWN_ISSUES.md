# MEMG Core - Limitations and Known Issues

This document tracks known limitations, design issues, and areas for improvement in the MEMG Core system.

## 🔴 Critical Database Limitations

### 1. ~~Kuzu Cannot Handle Same Predicate with Different Target Types~~ ✅ FIXED

**~~Issue~~**: ~~Kuzu graph database cannot create relationship tables where the same predicate connects to different target entity types.~~

**RESOLUTION (2025-01-30)**: This was **our bug**, not Kuzu's limitation. The issue was in our DDL generation code that tried to create multiple relationship tables with the same name but different schemas.

**VERIFICATION (2025-01-31)**: Comprehensive testing confirms this fix is working perfectly. Successfully created `ANNOTATES` relationships from notes to both documents and tasks, demonstrating the same predicate works with different target types.

**What We Fixed**:
- **GraphRegister**: Now generates unique table names using `SOURCE_PREDICATE_TARGET` pattern (e.g., `NOTE_ANNOTATES_DOCUMENT`, `NOTE_ANNOTATES_TASK`)
- **KuzuInterface**: Updated to use the unique table names in relationship creation and querying
- **Backward Compatibility**: API still accepts predicates like `["ANNOTATES"]` and internally expands them to match the appropriate table names

**Example - Now Works**:
```yaml
# This NOW WORKS perfectly:
note:
  relations:
    - predicates: [ANNOTATES]
      source: note
      target: document  # ✅ Creates NOTE_ANNOTATES_DOCUMENT table
    - predicates: [ANNOTATES]
      source: note
      target: task      # ✅ Creates NOTE_ANNOTATES_TASK table
```

**Benefits of the Fix**:
- ✅ Preserves semantic consistency - same predicate can be used across different target types
- ✅ Eliminates need for artificial predicate variations
- ✅ Scales to any number of entities and relationships
- ✅ Maintains backward compatibility with existing APIs

### 2. Enum Validation Not Enforced ⚠️ ACTIVE LIMITATION

**Issue**: YAML schema enum constraints are not validated at runtime, allowing invalid values to be stored.

**Current Behavior**:
```yaml
# Schema defines:
status: { type: enum, choices: [backlog, todo, in_progress, in_review, done, cancelled] }

# But system accepts ANY value:
status: "invalid_status"  # ❌ Should fail but is accepted and stored
status: "completed"       # ❌ Should fail but is accepted and stored
status: "pending"         # ❌ Should fail but is accepted and stored
```

**Impact**:
- Data integrity risk - invalid enum values can be stored
- Schema constraints are decorative, not functional
- Potential issues with filtering/querying on enum fields

**Status**: Active limitation - enum validation system needs implementation

**Tested Fields**: All enum fields affected (task.status, task.priority, bug.severity, bug.status, note.origin)

---

## 🟡 YAML Schema Design Issues

### 3. ~~Redundant Source Declaration~~ ✅ IMPROVED

**~~Issue~~**: ~~Current YAML schema redundantly declares `source` when it's already implied by the entity context.~~

**IMPROVEMENT (2025-01-31)**: Schema has been redesigned to eliminate redundancy and improve usability. The software_developer schema now includes comprehensive relationship coverage with consistent naming patterns.

### 4. ~~Missing Relationships & Asymmetric Design~~ ✅ IMPROVED

**~~Issue~~**: ~~Schema had asymmetric relationships and missing logical connections between entities.~~

**IMPROVEMENT (2025-01-31)**: Added comprehensive relationship coverage:

**New Relationships Added**:
- `note → bug`: `REPORTS` (notes can report bugs)
- `note → solution`: `DESCRIBES` (notes can describe solutions)
- `document → bug`: `DOCUMENTS` (documents can document bugs)
- `document → solution`: `SPECIFIES` (documents can specify solutions)
- `task → solution`: `SOLVED_BY` (tasks implemented by solutions)
- `bug → task`: `TRACKED_BY` (bugs tracked by tasks)
- `bug → solution`: `FIXED_BY` (bugs fixed by solutions)
- `note → note`: `RELATED_TO` (non-directed note relationships)

**Benefits Achieved**:
- Complete workflow coverage from bug → task → solution → documentation
- Bidirectional relationships where logical
- Enhanced search through graph traversal
- Consistent naming patterns (`source_predicate_target`)

### 5. Ambiguous `directed` Field with Multiple Predicates

**Issue**: The `directed: true/false` field is ambiguous when `predicates` is a list.

**Current Problem**:
```yaml
relations:
  - predicates: [FIXES, ADDRESSES, RESOLVES]  # Multiple predicates
    directed: true  # ← Which predicate(s) are directed?
```

**Questions**:
- Does `directed: true` apply to ALL predicates in the list?
- Can we have mixed directionality within the same relationship definition?
- How do we handle bidirectional vs unidirectional predicates?

**Needs Clarification**:
- Define clear semantics for `directed` with multiple predicates
- Consider predicate-level directionality specification
- Document expected behavior for relationship traversal

---

## 🟡 Unused/Underutilized Schema Features

### 6. Relationship `name` Field Usage

**Issue**: The `name` field in relationships appears to be used only for identification/annotation, not for functional purposes.

**Current Usage**:
```yaml
- name: solution_bug  # Used for what exactly?
  description: "Solution addressing a bug"
  predicates: [FIXES]
```

**Questions**:
- Is `name` used in queries or just documentation?
- Should it follow naming conventions?
- Could it be optional if only used for human readability?

### 7. Multiple Relationships to Same Target

**Issue**: Unclear how to define multiple relationship types between the same source-target pair.

**Example Need**:
```yaml
solution → bug relationships:
  - FIXES (solution resolves the bug)
  - RELATES_TO (solution mentions the bug)
  - CAUSED_BY (solution introduced the bug)
```

**Current Limitation**: Would require separate relationship definitions with potential naming conflicts.

---

## 🔵 Proposed Improvements

### 1. Target-First Relationship Organization

Reorganize YAML schema to group relationships by target entity:

```yaml
- name: solution
  relations:
    bug:
      - name: fixes_relationship
        predicates: [FIXES]
        directed: true
        description: "Solution that resolves a bug"
      - name: mentions_relationship
        predicates: [MENTIONS]
        directed: true
        description: "Solution that references a bug"
    task:
      - name: implements_relationship
        predicates: [IMPLEMENTS]
        directed: true
        description: "Solution that fulfills a task"
```

### 2. Predicate-Level Directionality

Allow directionality specification per predicate:

```yaml
relations:
  bug:
    - predicates:
        - name: FIXES
          directed: true
        - name: BIDIRECTIONAL_RELATES
          directed: false
```

### 3. Kuzu Relationship Table Strategy

Develop naming strategy to avoid predicate conflicts:
- Use entity-specific predicates: `NOTE_ANNOTATES_DOCUMENT`, `NOTE_COMMENTS_ON_TASK`
- Or implement relationship table namespacing in Kuzu interface

---

## 📋 Action Items

- [x] **High Priority**: ~~Resolve Kuzu same-predicate limitation~~ ✅ **COMPLETED (2025-01-30)**
- [x] **Medium Priority**: ~~Redesign YAML relationship schema for clarity~~ ✅ **COMPLETED (2025-01-31)**
- [ ] **High Priority**: Implement enum validation system ⚠️ **NEW**
- [ ] **Low Priority**: Clarify unused schema features
- [ ] **Documentation**: Add relationship modeling best practices
- [x] **Testing**: ~~Create comprehensive relationship test suite~~ ✅ **COMPLETED (2025-01-31)**

---

## 🔍 Investigation Needed

1. **Kuzu Capabilities**: Research if newer Kuzu versions support multi-target predicates
2. **Alternative Approaches**: Investigate relationship table naming strategies
3. **Schema Migration**: Plan for YAML schema evolution without breaking changes
4. **Performance Impact**: Measure relationship query performance with current limitations

---

## 🧪 **Comprehensive Testing Methodology**

### **How to Run Complete MEMG System Tests**

**Prerequisites:**
1. Start MCP server with target directory approach: `./cli.sh --target-path ./software_developer/ --rebuild-safe`
2. Ensure fresh database (delete memory data folder if needed)
3. Connect to MCP tools in development environment

**Testing Heuristics:**

#### **1. Core Functionality Tests**
```bash
# Test basic memory operations
- Add memories of each type (note, document, task, bug, solution, memo)
- Search memories with semantic queries
- Verify health_check and get_system_info responses
```

#### **2. Relationship Network Tests**
```bash
# Test all schema-defined relationships
- Create realistic software development scenario
- Add relationships: bug→solution, task→solution, note→bug, etc.
- Verify relationship creation success
- Test non-directed relationships (note↔note)
```

#### **3. Enhanced Search Tests**
```bash
# Test graph traversal in search results
- Search for terms that should trigger relationship traversal
- Verify "graph_neighbor" results appear with relation_type metadata
- Confirm semantic + relationship search provides comprehensive coverage
```

#### **4. Schema Validation Tests**
```bash
# Test enum constraint enforcement (currently fails)
- Try valid enum values (should work)
- Try invalid enum values (currently accepted, should fail)
- Document validation gaps for future fixes
```

#### **5. Edge Case Tests**
```bash
# Test system boundaries
- Test relationship combinations not defined in schema (should fail)
- Test user_id isolation
- Test memory type inheritance behavior
```

**Expected Results:**
- ✅ All schema-defined relationships work
- ✅ Graph traversal enhances search results
- ✅ Core CRUD operations function correctly
- ⚠️ Enum validation currently not enforced (known limitation)

**Test Data Strategy:**
Create coherent software development workflow: bug report → task creation → solution implementation → documentation → notes. This provides realistic relationship testing and meaningful search scenarios.

---

*Last Updated: 2025-01-31*
*Contributors: Development Team*
