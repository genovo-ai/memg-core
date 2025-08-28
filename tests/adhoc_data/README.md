# MEMG-Core Test Data

This directory contains rich test datasets for comprehensive E2E testing of memg-core.

## Files

### `software_dev.json`
Rich test dataset representing a software development project with:
- **5 notes** - Various observations about the system architecture and design
- **3 tasks** - Development work items with different priorities and statuses
- **2 bugs** - Real issues that were found and resolved during development
- **1 solution** - Fix for one of the bugs
- **1 document** - Architecture documentation
- **6 relationships** - Realistic connections between memories (ADDRESSES, FIXES, ANNOTATES, SUPPORTS, BLOCKS)

### `load_test_data.py`
Python script to load the test dataset into memg-core:
- Creates all memories and tracks their HRIDs
- Sets up relationships between memories (when relationship API is implemented)
- Tests search functionality with realistic queries
- Provides comprehensive E2E validation

## Usage

```bash
# Run the E2E test with rich data
python tests/adhoc_data/load_test_data.py

# Or make it executable and run directly
chmod +x tests/adhoc_data/load_test_data.py
./tests/adhoc_data/load_test_data.py
```

## Dataset Structure

The JSON dataset follows this structure:

```json
{
  "description": "Dataset description",
  "project": "project-name",
  "user_id": "user-identifier",
  "memories": [
    {
      "type": "note|task|bug|solution|document",
      "payload": { /* entity-specific fields */ },
      "hrid_key": "unique_key_for_relationships"
    }
  ],
  "relationships": [
    {
      "description": "Human-readable description",
      "source_key": "source_hrid_key",
      "target_key": "target_hrid_key",
      "relation_type": "ADDRESSES|FIXES|ANNOTATES|SUPPORTS|BLOCKS"
    }
  ]
}
```

## Benefits

1. **Realistic Testing** - Uses actual development scenarios rather than artificial test data
2. **Relationship Validation** - Tests the full graph capabilities with meaningful connections
3. **Search Quality** - Validates semantic search with diverse, realistic content
4. **HRID Tracking** - Demonstrates proper HRID management for relationship creation
5. **Scalable Template** - Easy to extend with more entities, types, or relationships

## Extending

To add more test data:
1. Add new memories to the `memories` array
2. Give each memory a unique `hrid_key`
3. Add relationships using the `hrid_key` references
4. Run the loader script to validate

This approach makes E2E testing much more practical than writing hundreds of unit tests!
