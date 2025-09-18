#!/usr/bin/env python3
"""
ADK + memg-core Personal Assistant: Smart & Simple

A focused, schema-driven memory system in ~120 lines that demonstrates
the power of combining Google ADK with memg-core's YAML-driven architecture.

Features:
- Two-tier memory: Notes (preferences) + Instructions (AI behavior)
- Universal RELATED_TO relationships (no complex relation types)
- Smart search and behavioral guidance
- All functions generated from YAML schema
"""

import datetime
from typing import Dict, Any, Optional
from pathlib import Path

from memg_core.api.public import MemgClient
from memg_core.core.yaml_translator import YamlTranslator

# =============================================================================
# SETUP
# =============================================================================

def init_memg_core() -> tuple[MemgClient, YamlTranslator]:
    """Initialize memg-core client and YAML translator."""
    current_dir = Path(__file__).parent
    yaml_path = current_dir / "personal_assistant.yaml"
    db_path = current_dir.parent / "db"

    if not yaml_path.exists():
        raise FileNotFoundError(f"Schema not found: {yaml_path}")

    db_path.mkdir(exist_ok=True)

    client = MemgClient(str(yaml_path.absolute()), str(db_path.absolute()))
    translator = YamlTranslator(str(yaml_path.absolute()))

    return client, translator

# Initialize once
memg_client, yaml_translator = init_memg_core()

# =============================================================================
# PAYLOAD TRANSFORMATION HELPERS (following MCP server pattern)
# =============================================================================

def _format_datetime_simple(dt_str: str) -> str:
    """Convert ISO datetime to simple format: '2025-09-04 21:55:11'"""
    if not dt_str:
        return dt_str
    try:
        # Handle both with and without timezone
        if 'T' in dt_str:
            date_part, time_part = dt_str.split('T')
            if '+' in time_part:
                time_part = time_part.split('+')[0]
            elif 'Z' in time_part:
                time_part = time_part.replace('Z', '')
            # Take only seconds precision (remove microseconds if present)
            if '.' in time_part:
                time_part = time_part.split('.')[0]
            return f"{date_part} {time_part}"
        return dt_str
    except Exception:
        return dt_str

def _flatten_memory_payload(memory_data: Dict[str, Any]) -> Dict[str, Any]:
    """Flatten memory payload structure for consistent API responses."""
    if not memory_data:
        return memory_data

    # Start with system fields from root level
    flattened = {
        "hrid": memory_data.get("hrid"),
        "memory_type": memory_data.get("memory_type"),
        "user_id": memory_data.get("user_id")
    }

    # Add formatted timestamps from root level
    if memory_data.get("created_at"):
        flattened["created_at"] = _format_datetime_simple(memory_data["created_at"])
    if memory_data.get("updated_at"):
        flattened["updated_at"] = _format_datetime_simple(memory_data["updated_at"])

    # Handle payload structure - flatten it into root level
    payload = memory_data.get("payload", {})
    if isinstance(payload, dict):
        for key, value in payload.items():
            # Skip system fields and metadata that shouldn't be at user level
            if key not in ["hrid", "memory_type", "user_id", "created_at", "updated_at", "_label", "vector"]:
                flattened[key] = value

        # If payload has its own timestamps (from list operations), use those instead
        if payload.get("created_at") and not memory_data.get("created_at"):
            flattened["created_at"] = _format_datetime_simple(payload["created_at"])
        if payload.get("updated_at") and not memory_data.get("updated_at"):
            flattened["updated_at"] = _format_datetime_simple(payload["updated_at"])

    # Add score if present (from search results)
    if "score" in memory_data:
        flattened["score"] = memory_data["score"]

    # Add relationships if present
    if "relationships" in memory_data:
        flattened["relationships"] = memory_data["relationships"]

    # Add any other root-level fields that aren't system fields
    for key, value in memory_data.items():
        if key not in ["hrid", "memory_type", "user_id", "created_at", "updated_at", "payload", "score", "relationships"]:
            flattened[key] = value

    return flattened

def _enhance_relationship_with_context(relationship: Dict[str, Any], target_memories: Dict[str, Dict]) -> Dict[str, Any]:
    """Add anchor field context to relationship objects using YAML-defined anchor field."""
    enhanced = relationship.copy()
    target_hrid = relationship.get("target_hrid")

    if target_hrid and target_hrid in target_memories:
        target_memory = target_memories[target_hrid]
        if isinstance(target_memory, dict):
            memory_type = target_memory.get("memory_type")
            if memory_type and yaml_translator:
                try:
                    # Get the anchor field dynamically from YAML schema
                    anchor_field = yaml_translator.get_anchor_field(memory_type)

                    # Look for anchor field in payload first, then in root
                    payload = target_memory.get("payload", {})
                    anchor_text = None

                    if isinstance(payload, dict) and anchor_field in payload:
                        anchor_text = payload[anchor_field]
                    elif anchor_field in target_memory:
                        anchor_text = target_memory[anchor_field]

                    if anchor_text:
                        # Use the actual field name as the key instead of generic names
                        enhanced[anchor_field] = anchor_text

                except Exception as e:
                    # Silent fallback - don't break search results
                    pass

    return enhanced

# =============================================================================
# MEMORY FUNCTIONS
# =============================================================================

def add_note(content: str, category: Optional[str] = None) -> Dict[str, Any]:
    """
    Add a note for user preferences and everyday information.

    Args:
        content: The note content to remember
        category: Optional category (e.g., "preferences", "work", "personal")

    Returns:
        Dict with status and HRID
    """
    try:
        payload = {"content": content.strip()}
        if category and category.strip():
            payload["category"] = category.strip()

        hrid = memg_client.add_memory("note", payload, "adk_user")
        return {
            "status": "success",
            "message": f"Note saved with ID: {hrid}",
            "hrid": hrid
        }
    except Exception as e:
        return {"status": "error", "message": f"Failed to add note: {str(e)}"}

def add_instruction(summary: str, details: str) -> Dict[str, Any]:
    """
    Add a behavioral instruction for long-term AI guidance.

    Args:
        summary: Brief summary of the instruction
        details: Detailed behavioral guidance

    Returns:
        Dict with status and HRID
    """
    try:
        payload = {
            "summary": summary.strip(),
            "details": details.strip()
        }

        hrid = memg_client.add_memory("instruction", payload, "adk_user")
        return {
            "status": "success",
            "message": f"Instruction saved with ID: {hrid}",
            "hrid": hrid
        }
    except Exception as e:
        return {"status": "error", "message": f"Failed to add instruction: {str(e)}"}

def search_memory(query: str, memory_type: Optional[str] = None, limit: int = 5, include_neighbors: bool = True) -> Dict[str, Any]:
    """
    Search through memories using semantic similarity with graph expansion.

    Args:
        query: Search query text
        memory_type: Filter by "note" or "instruction" (optional)
        limit: Maximum results to return
        include_neighbors: Include related memories through graph relationships

    Returns:
        Dict with search results including memories and neighbors
    """
    try:
        if not query.strip():
            return {"status": "error", "message": "Query cannot be empty"}

        # Validate memory type
        if memory_type and memory_type not in ["note", "instruction"]:
            return {"status": "error", "message": "memory_type must be 'note' or 'instruction'"}

        # Search with graph expansion - following MCP server pattern
        results = memg_client.search(
            query=query.strip(),
            user_id="adk_user",
            memory_type=memory_type,
            limit=min(max(limit, 1), 20),  # Clamp between 1-20
            score_threshold=0.7,
            hops=2 if include_neighbors else 0,
            neighbor_limit=5,
            decay_rate=0.8
        )

        # Convert SearchResult to dict following MCP server pattern
        search_dict = results.model_dump()

        # Create neighbor lookup for relationship enhancement
        neighbor_lookup = {}
        flattened_neighbors = []

        for neighbor in search_dict.get("neighbors", []):
            flattened_neighbor = _flatten_memory_payload(neighbor)
            flattened_neighbors.append(flattened_neighbor)
            neighbor_lookup[neighbor.get("hrid")] = neighbor

        # Flatten seed memories and enhance relationships
        flattened_memories = []
        for memory in search_dict.get("memories", []):
            flattened_memory = _flatten_memory_payload(memory)

            # Enhance relationships with target context
            if "relationships" in flattened_memory:
                enhanced_relationships = []
                for rel in flattened_memory["relationships"]:
                    enhanced_rel = _enhance_relationship_with_context(rel, neighbor_lookup)
                    enhanced_relationships.append(enhanced_rel)
                flattened_memory["relationships"] = enhanced_relationships

            flattened_memories.append(flattened_memory)

        return {
            "status": f"Found {len(results.memories)} memories and {len(results.neighbors)} neighbors",
            "memories": flattened_memories,
            "neighbors": flattened_neighbors,
            "query": query,
            "user_id": "adk_user",
            "search_params": {
                "limit": limit,
                "memory_type": memory_type,
                "neighbor_limit": 5,
                "hops": 2 if include_neighbors else 0,
                "include_neighbors": include_neighbors
            }
        }
    except Exception as e:
        return {"status": "error", "message": f"Search failed: {str(e)}"}

def get_instructions() -> Dict[str, Any]:
    """
    Get all behavioral instructions for AI guidance.
    The AI should check these frequently to know how to behave.

    Returns:
        Dict with all instructions
    """
    try:
        memories = memg_client.get_memories(
            user_id="adk_user",
            memory_type="instruction",
            limit=100  # Get all instructions
        )

        instructions = []
        for memory in memories:
            payload = memory.get("payload", {})
            instructions.append({
                "hrid": memory["hrid"],
                "summary": payload.get("summary", "ERROR IN GET_INSTRUCTIONS - SUMMARY"),
                "details": payload.get("details", "ERROR IN GET_INSTRUCTIONS - DETAILS"),
                "created_at": memory["created_at"]
            })

        return {
            "status": "success",
            "total_instructions": len(instructions),
            "instructions": instructions
        }
    except Exception as e:
        return {"status": "error", "message": f"Failed to get instructions: {str(e)}"}

def update_instruction(hrid: str, summary: Optional[str] = None, details: Optional[str] = None) -> Dict[str, Any]:
    """
    Update an existing instruction's summary or details.

    Args:
        hrid: Instruction HRID (e.g., "INSTRUCTION_XYZ789")
        summary: New brief summary (optional)
        details: New detailed guidance (optional)

    Returns:
        Dict with update status
    """
    try:
        if not hrid.strip():
            return {"status": "error", "message": "HRID cannot be empty"}

        if not hrid.upper().startswith("INSTRUCTION_"):
            return {"status": "error", "message": "HRID must be for an instruction"}

        updates = {}
        if summary is not None and summary.strip():
            updates["summary"] = summary.strip()
        if details is not None and details.strip():
            updates["details"] = details.strip()

        if not updates:
            return {"status": "error", "message": "No valid updates provided"}

        success = memg_client.update_memory(
            hrid=hrid.strip(),
            user_id="adk_user",
            payload_updates=updates
        )

        if success:
            updated_fields = ", ".join(updates.keys())
            return {
                "status": "success",
                "message": f"Instruction {hrid} updated successfully",
                "updated_fields": updated_fields
            }
        else:
            return {"status": "error", "message": f"Instruction {hrid} not found"}
    except Exception as e:
        return {"status": "error", "message": f"Failed to update instruction: {str(e)}"}

def delete_memory(hrid: str) -> Dict[str, Any]:
    """
    Delete a memory by its HRID.

    Args:
        hrid: Human-readable ID (e.g., "NOTE_ABC123", "INSTRUCTION_XYZ789")

    Returns:
        Dict with deletion status
    """
    try:
        if not hrid.strip():
            return {"status": "error", "message": "HRID cannot be empty"}

        success = memg_client.delete_memory(hrid=hrid.strip(), user_id="adk_user")

        if success:
            return {"status": "success", "message": f"Memory {hrid} deleted successfully"}
        else:
            return {"status": "error", "message": f"Memory {hrid} not found or already deleted"}
    except Exception as e:
        return {"status": "error", "message": f"Failed to delete memory: {str(e)}"}

def add_relation(from_hrid: str, to_hrid: str) -> Dict[str, Any]:
    """
    Add a RELATED_TO relationship between two memories.

    Args:
        from_hrid: Source memory HRID
        to_hrid: Target memory HRID

    Returns:
        Dict with relation status
    """
    try:
        if not from_hrid.strip() or not to_hrid.strip():
            return {"status": "error", "message": "Both HRIDs are required"}

        # Extract memory types from HRIDs (e.g., "NOTE_ABC123" -> "note")
        from_type = "_".join(from_hrid.split("_")[:-1]).lower()
        to_type = "_".join(to_hrid.split("_")[:-1]).lower()

        if from_type not in ["note", "instruction"] or to_type not in ["note", "instruction"]:
            return {"status": "error", "message": "Invalid memory types in HRIDs"}

        memg_client.add_relationship(
            from_memory_hrid=from_hrid.strip(),
            to_memory_hrid=to_hrid.strip(),
            relation_type="RELATED_TO",
            from_memory_type=from_type,
            to_memory_type=to_type,
            user_id="adk_user"
        )

        return {
            "status": "success",
            "message": f"Relationship added: {from_hrid} RELATED_TO {to_hrid}"
        }
    except Exception as e:
        return {"status": "error", "message": f"Failed to add relationship: {str(e)}"}

# =============================================================================
# UTILITY FUNCTIONS
# =============================================================================

def get_current_time() -> Dict[str, Any]:
    """Get current date and time information."""
    now = datetime.datetime.now()
    return {
        "status": "success",
        "current_time": now.isoformat(),
        "formatted_time": now.strftime("%Y-%m-%d %H:%M:%S"),
        "day_of_week": now.strftime("%A")
    }

def memory_stats() -> Dict[str, Any]:
    """Get statistics about stored memories."""
    try:
        # Get counts for each type
        notes = memg_client.get_memories("adk_user", memory_type="note", limit=1000)
        instructions = memg_client.get_memories("adk_user", memory_type="instruction", limit=1000)

        return {
            "status": "success",
            "total_memories": len(notes) + len(instructions),
            "notes": len(notes),
            "instructions": len(instructions),
            "user_id": "adk_user"
        }
    except Exception as e:
        return {"status": "error", "message": f"Failed to get stats: {str(e)}"}

# =============================================================================
# EXPORT FOR ADK
# =============================================================================

# All available tools for ADK agent
TOOLS = [
    add_note,
    add_instruction,
    search_memory,
    get_instructions,
    update_instruction,
    delete_memory,
    add_relation,
    get_current_time,
    memory_stats
]
