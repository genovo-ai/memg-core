# MEMG Core - Future Template System

🚧 **This directory contains materials for future template development**

## Current Status (Lean Core)

The current lean core uses a **single fixed schema**:
- **File**: `config/core.minimal.yaml`
- **Entities**: `note`, `document`, `task`
- **No template switching** - uses fixed entity types

## Vision for Future Template System

### 📋 **Template Use Cases**

Templates should provide **predefined memo types + relationships** for specific domains:

#### 🏢 **Software Development Template**
```yaml
entities:
  - bug_report: { anchor: summary, fields: [severity, assignee, status] }
  - feature_request: { anchor: summary, fields: [priority, epic, story_points] }
  - code_review: { anchor: summary, fields: [reviewer, status, files_changed] }
  - meeting_notes: { anchor: summary, fields: [attendees, action_items] }
  - documentation: { anchor: summary, fields: [version, category] }

relations:
  - bug_blocks_feature: { source: bug_report, target: feature_request }
  - review_covers_feature: { source: code_review, target: feature_request }
  - meeting_discusses_bug: { source: meeting_notes, target: bug_report }
```

#### 🎓 **Research/Academic Template**
```yaml
entities:
  - research_paper: { anchor: abstract, fields: [authors, journal, year] }
  - experiment: { anchor: hypothesis, fields: [methodology, results] }
  - literature_note: { anchor: summary, fields: [source, relevance] }
  - idea: { anchor: description, fields: [status, related_papers] }

relations:
  - paper_cites_paper: { source: research_paper, target: research_paper }
  - experiment_tests_idea: { source: experiment, target: idea }
  - note_summarizes_paper: { source: literature_note, target: research_paper }
```

#### 💼 **Business/Project Template**
```yaml
entities:
  - project: { anchor: description, fields: [status, deadline, budget] }
  - milestone: { anchor: description, fields: [due_date, completion] }
  - stakeholder: { anchor: description, fields: [role, contact] }
  - risk: { anchor: description, fields: [probability, impact, mitigation] }

relations:
  - project_has_milestone: { source: project, target: milestone }
  - stakeholder_owns_project: { source: stakeholder, target: project }
  - risk_affects_project: { source: risk, target: project }
```

### 🔧 **Implementation Strategy**

1. **Keep lean core simple** - Single `core.minimal.yaml` for now
2. **Build template system later** - When we need domain-specific types
3. **Template structure**:
   ```
   templates/
   ├── software_development.yaml
   ├── research_academic.yaml
   ├── business_project.yaml
   └── personal_knowledge.yaml
   ```

4. **Environment variable**: `MEMG_TEMPLATE=software_development`
5. **Backward compatibility**: Default to `core.minimal.yaml`

### 📚 **Reference Materials**

- `old_templates/` - Legacy template system from old MEMG-Core
- `config/core.minimal.yaml` - Current lean core schema
- MCP server supports: `add_note`, `add_document`, `add_task`, `search`

### 🎯 **Next Steps (Future)**

1. Design template YAML schema format
2. Implement template loading in `core/config.py`
3. Update MCP server to support dynamic entity types
4. Create domain-specific templates
5. Add template validation and testing

---

**Note**: This is future work. Current lean core works perfectly with the fixed schema!
