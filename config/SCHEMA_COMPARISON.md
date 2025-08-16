# MEMG Schema Enhancement: Software Developer AI

## Overview

Enhanced the minimal schema (`core.minimal.yaml`) to create a software developer-focused schema (`core.software_dev.yaml`) that stays lean but significantly more useful for AI development workflows.

## Key Enhancements

### 1. New Entity Types (4 added)

#### `bug` - Bug tracking and issue management
- **Fields**: `severity`, `status`, `reproduction`, `environment`, `file_path`, `line_number`
- **Relations**: Links to solutions and tasks
- **Use case**: Track bugs with context, reproduction steps, and file locations

#### `solution` - Implementation approaches and fixes
- **Fields**: `approach`, `code_snippet`, `file_path`, `test_status`
- **Relations**: Fixes bugs, implements tasks
- **Use case**: Store code solutions, approaches, and implementation details

#### `code_review` - Code review feedback
- **Fields**: `review_type`, `file_path`, `line_range`, `reviewer`, `status`
- **Relations**: Suggests solutions
- **Use case**: Capture code review feedback with precise file/line context

#### `learning` - Knowledge and insights
- **Fields**: `category`, `difficulty`, `source`
- **Relations**: Influences solutions, relates to other learnings
- **Use case**: Store programming insights, patterns, gotchas, best practices

### 2. Enhanced Existing Types

#### `memo` (base type)
- **Added**: `tags` field for categorization

#### `document`
- **Added**: `url` field for external references

#### `task`
- **Added**: `story_points`, `epic` fields for agile workflows
- **Enhanced**: New `task_blocks` relation for dependency tracking

### 3. Rich Relationship Network

```
bug ←→ solution ←→ task
 ↑        ↑        ↑
 └─ code_review ──┘
         ↑
    learning ────→ solution
```

## Schema Comparison

| Feature | Minimal | Software Dev | Enhancement |
|---------|---------|--------------|-------------|
| Entity types | 4 | 8 | +4 new types |
| Bug tracking | ❌ | ✅ | Full bug lifecycle |
| Code context | ❌ | ✅ | File paths, line numbers |
| Review process | ❌ | ✅ | Code review workflow |
| Learning capture | ❌ | ✅ | Knowledge management |
| Agile support | Basic | ✅ | Story points, epics |
| Code snippets | ❌ | ✅ | Embedded code examples |

## Usage Examples

### Bug Tracking
```yaml
memory_type: bug
payload:
  statement: "Authentication fails on mobile Safari"
  details: "Users can't login on iOS Safari 15+"
  severity: high
  status: investigating
  reproduction: "1. Open Safari on iOS, 2. Navigate to login..."
  environment: "iOS Safari 15.6, iPhone 13"
  file_path: "src/auth/login.tsx"
  line_number: "145"
```

### Solution Storage
```yaml
memory_type: solution
payload:
  statement: "Fix Safari authentication issue"
  details: "Add user-agent detection and fallback auth method"
  approach: proper_fix
  code_snippet: "if (isSafari && isIOS) { usePolyfill() }"
  file_path: "src/auth/login.tsx"
  test_status: unit_test
```

### Learning Capture
```yaml
memory_type: learning
payload:
  statement: "Safari has different cookie behavior in private mode"
  details: "Third-party cookies blocked by default, affects OAuth flows"
  category: gotcha
  difficulty: intermediate
  source: "debugging session"
```

## Benefits for Software Developer AI

1. **Context-Rich Bug Tracking**: Capture bugs with file locations, reproduction steps
2. **Solution Knowledge Base**: Store code snippets and approaches with context
3. **Code Review Integration**: Track feedback with precise file/line references
4. **Learning Accumulation**: Build knowledge base of patterns, gotchas, best practices
5. **Agile Workflow Support**: Story points, epics, task dependencies
6. **Rich Relationships**: Connect bugs to solutions, reviews to improvements

## Maintains MEMG Principles

- ✅ **Lean**: Only 4 new types, focused on core dev workflows
- ✅ **YAML-driven**: Full schema compliance, no hardcoded types
- ✅ **Inheritance**: All new types extend memo base
- ✅ **Relationships**: Rich but purposeful connections
- ✅ **Extensible**: Easy to add more dev-specific types later

The enhanced schema transforms MEMG from a general memory system into a powerful AI assistant for software development workflows while maintaining its lightweight, YAML-driven architecture.
