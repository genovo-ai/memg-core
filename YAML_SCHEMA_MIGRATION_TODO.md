# YAML Schema Migration TODO

## Current Problem

The YAML schema feature is currently **DISABLED BY DEFAULT** but the README suggests it's a core feature. This is inconsistent and confusing.

## What YAML Schema Does

- **Entity/Relationship Catalogs**: Defines types like `note`, `document`, `task`, `bug`, `solution`
- **Anchor Fields**: Specifies which field to use for indexing (e.g., `summary` for documents)
- **Relation Names**: Defines relationship types like `mentions`, `bug_solution`

## Current Issues

1. **Feature is optional** (`MEMG_ENABLE_YAML_SCHEMA=false` by default)
2. **Integration configs missing** (README mentions `integration/config/` but directory doesn't exist)
3. **Try/except blocks** for "optional" imports when it should be core
4. **Documentation inconsistency** - README says it "ships with" YAML configs but they're missing

## Files Affected

- `src/memg_core/plugins/yaml_schema.py` - The plugin itself
- `src/memg_core/api/public.py` - Two try/except blocks for optional imports
- `src/memg_core/system/info.py` - Feature detection
- `README.md` - Claims feature exists and configs ship with core

## Decision Needed

### Option A: Make YAML Schema Core (Recommended)
- Remove `MEMG_ENABLE_YAML_SCHEMA` env var checks
- Remove try/except "plugin is optional" blocks
- Create the missing `integration/config/` YAML files
- Make YAML schema always enabled

### Option B: Make YAML Schema Truly Optional
- Remove from README as core feature
- Document as advanced/optional feature
- Keep current plugin architecture

### Option C: Remove YAML Schema Entirely
- Delete the plugin
- Simplify codebase
- Remove all references

## Recommendation

**Option A** - Make it core. The code suggests this was intended to be a core feature but got left half-implemented. The try/except blocks and environment variable checks are just technical debt.

## Next Steps

1. **Decide** which option to pursue
2. **Create YAML configs** if going with Option A
3. **Remove try/except blocks** and make imports direct
4. **Update documentation** to match reality
5. **Test** the feature properly

---

*Created during try/except cleanup - this "optional" plugin should probably be core.*
