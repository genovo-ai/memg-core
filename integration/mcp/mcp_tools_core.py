#!/usr/bin/env python3
"""
MEMG Core MCP Tools - The Essential 6 Tools
Clean implementations of the core memory management tools
"""

import os
from typing import Optional

from fastmcp import FastMCP

from memory_system.logging_config import log_error
from memory_system.models.api import MemoryResultItem, SearchMemoriesResponse
from memory_system.utils.genai import GenAI

from .mcp_server_core import get_memory_system


def register_core_tools(app: FastMCP) -> None:
    """Register the 6 core MCP tools"""

    @app.tool("add_memory")
    def add_memory(
        content: str,
        user_id: str,
        memory_type: str = None,
        source: str = "mcp_api",
        title: str = None,
        tags: str = None,
    ):
        """Add a memory to the g^mem system with optional type specification."""
        memory = get_memory_system()
        if not memory:
            return {"result": "❌ Memory system not initialized"}

        try:
            from memory_system.models.core import MemoryType

            # Parse memory_type
            parsed_memory_type = None
            if memory_type:
                memory_type = memory_type.upper()
                if memory_type in ["DOCUMENT", "NOTE", "CONVERSATION"]:
                    parsed_memory_type = MemoryType[memory_type]
                else:
                    return {
                        "result": f"❌ Invalid memory_type: {memory_type}. Use 'document', 'note', or 'conversation'"
                    }

            # Parse tags
            parsed_tags = []
            if tags:
                parsed_tags = [tag.strip() for tag in tags.split(",") if tag.strip()]

            # Add memory
            response = memory.add(
                content=content,
                user_id=user_id,
                memory_type=parsed_memory_type,
                title=title,
                source=source,
                tags=parsed_tags,
            )

            if response.success:
                return {
                    "result": "✅ Memory added successfully",
                    "memory_id": response.memory_id,
                    "final_type": response.final_type.value,
                    "ai_verified": response.ai_verified,
                    "processing_time_ms": response.processing_time_ms,
                    "word_count": response.word_count,
                }
            else:
                return {"result": "❌ Failed to add memory"}

        except Exception as e:
            log_error("mcp_tools_core", "add_memory", e, content_length=len(content))
            return {"result": f"❌ Failed to add memory: {str(e)}"}

    @app.tool("search_memories")
    def search_memories(
        query: str,
        user_id: str,
        limit: int = 5,
        entity_types: str = None,
        project_id: str = None,
        days_back: int = None,
    ):
        """Search memories using semantic similarity with optional metadata filtering."""
        memory = get_memory_system()
        if not memory:
            return {"result": "❌ Memory system not initialized"}

        try:
            # Build filters dict from parameters
            filters = {}
            if entity_types:
                filters["entity_types"] = [
                    t.strip().upper() for t in entity_types.split(",") if t.strip()
                ]
            if project_id:
                filters["project_id"] = project_id
            if days_back is not None and days_back > 0:
                filters["days_back"] = days_back

            # Search memories
            results = memory._run_async(
                memory.retriever.search_memories(
                    query=query,
                    user_id=user_id,
                    filters=filters if filters else None,
                    limit=limit,
                )
            )

            # Format results
            formatted_results = [
                MemoryResultItem.from_search_result(result) for result in results
            ]
            response = SearchMemoriesResponse(
                result=formatted_results,
                query=query,
                total_results=len(formatted_results),
                filters_applied=filters or {},
                search_type="semantic_search",
                user_id=user_id,
            )

            return response.model_dump()

        except Exception as e:
            log_error("mcp_tools_core", "search_memories", e, query=query, limit=limit)
            return {"result": f"❌ Failed to search memories: {str(e)}"}

    @app.tool("graph_search")
    def graph_search(
        query: str, user_id: str = None, entity_types: str = None, limit: int = 10
    ):
        """Generic graph search over entities mentioned in memories."""
        memory = get_memory_system()
        if not memory:
            return {"result": "❌ Memory system not initialized"}

        try:
            types_list = None
            if entity_types:
                types_list = [
                    t.strip().upper() for t in entity_types.split(",") if t.strip()
                ]

            results = memory._run_async(
                memory.retriever.graph_search(
                    query=query,
                    entity_types=types_list or [],
                    limit=limit,
                    user_id=user_id,
                )
            )

            formatted_results = [
                MemoryResultItem.from_search_result(r) for r in results
            ]
            response = SearchMemoriesResponse(
                result=formatted_results,
                query=query,
                total_results=len(formatted_results),
                filters_applied={"entity_types": types_list or []},
                search_type="graph_search",
                user_id=user_id,
            )
            return response.model_dump()

        except Exception as e:
            log_error("mcp_tools_core", "graph_search", e, query=query, user_id=user_id)
            return {"result": f"❌ Graph search error: {str(e)}"}

    @app.tool("validate_graph")
    def validate_graph(user_id: str = None, validation_type: str = "comprehensive"):
        """Validate GraphRAG Stage 1 implementation - entity extraction and graph storage."""
        memory = get_memory_system()
        if not memory:
            return {"result": "❌ Memory system not initialized"}

        try:
            from memory_system.validation.graph_validator import GraphValidator

            validator = GraphValidator(memory.processor.kuzu)

            if validation_type == "comprehensive":
                report = validator.run_comprehensive_validation(user_id)
                return {
                    "result": f"✅ GraphRAG validation complete - Health Score: {report['overall_health_score']}/100",
                    "validation_report": report,
                    "summary": {
                        "entities": report["validation_results"]["entity_storage"][
                            "entity_count"
                        ],
                        "relationships": report["validation_results"]["relationships"][
                            "relationship_count"
                        ],
                        "memory_connections": f"{report['validation_results']['memory_connections'].get('connection_rate_percent', 0)}%",
                    },
                }
            elif validation_type == "entities":
                entities_report = validator.validate_entity_storage(user_id)
                coding_report = validator.validate_coding_entities(user_id)
                return {
                    "result": f"✅ Entity validation complete - {entities_report['entity_count']} total entities",
                    "entities": entities_report,
                    "coding_entities": coding_report,
                }
            elif validation_type == "relationships":
                rel_report = validator.validate_relationships(user_id)
                return {
                    "result": f"✅ Relationship validation complete - {rel_report['relationship_count']} relationships",
                    "relationships": rel_report,
                }
            elif validation_type == "connections":
                conn_report = validator.validate_memory_entity_connections(user_id)
                return {
                    "result": f"✅ Connection validation complete - {conn_report.get('connection_rate_percent', 0)}% memories have entities",
                    "connections": conn_report,
                }
            else:
                return {
                    "result": f"❌ Invalid validation_type: {validation_type}. Use 'comprehensive', 'entities', 'relationships', or 'connections'"
                }

        except Exception as e:
            log_error(
                "mcp_tools_core",
                "validate_graph",
                e,
                user_id=user_id,
                validation_type=validation_type,
            )
            return {"result": f"❌ Graph validation error: {str(e)}"}

    @app.tool("get_memory_schema")
    def get_memory_schema(user_id: str = None, include_stats: bool = True):
        """Get comprehensive schema information for intelligent AI filtering and discovery."""
        memory = get_memory_system()
        if not memory:
            return {"result": "❌ Memory system not initialized"}

        try:
            from memory_system.models.core import (
                EntityType,
                ImportanceLevel,
                MemoryType,
                RelationshipStrength,
                RelationshipType,
            )

            schema_info = {
                "memory_types": {
                    "available_types": [t.value for t in MemoryType],
                    "descriptions": {
                        "document": "Technical documentation, articles, guides with AI summary",
                        "note": "Brief notes, observations, ideas",
                        "conversation": "Chat messages, dialogue",
                    },
                },
                "entity_types": {
                    "available_types": [t.value for t in EntityType],
                    "categories": {
                        "technology": ["TECHNOLOGY", "DATABASE", "LIBRARY", "TOOL"],
                        "system": ["COMPONENT", "SERVICE", "ARCHITECTURE", "PROTOCOL"],
                        "problem_solution": [
                            "ERROR",
                            "ISSUE",
                            "SOLUTION",
                            "WORKAROUND",
                        ],
                        "domain": ["CONCEPT", "METHOD", "CONFIGURATION", "FILE_TYPE"],
                    },
                    "total_count": len(EntityType),
                },
                "relationship_types": {
                    "available_types": [t.value for t in RelationshipType],
                    "descriptions": {
                        "MENTIONED_IN": "Entity is mentioned in a memory",
                        "RELATES_TO": "General relationship between entities",
                        "USED_IN": "Entity is used within another context",
                        "WORKS_WITH": "Entities work together",
                        "PART_OF": "Entity is part of a larger system",
                        "SIMILAR_TO": "Entities have similar characteristics",
                    },
                },
                "relationship_strengths": [s.value for s in RelationshipStrength],
                "importance_levels": [i.value for i in ImportanceLevel],
                "filterable_fields": {
                    "memory_filters": [
                        "memory_type",
                        "project_id",
                        "source",
                        "tags",
                        "created_at",
                        "confidence",
                    ],
                    "entity_filters": [
                        "entity_types",
                        "importance_level",
                        "confidence",
                    ],
                    "temporal_filters": [
                        "days_back",
                        "created_after",
                        "created_before",
                    ],
                },
            }

            # Add usage statistics if requested
            if include_stats:
                try:
                    kuzu = memory.processor.kuzu

                    # Get basic stats
                    if user_id:
                        entity_stats = kuzu.query(
                            "MATCH (e:Entity) WHERE e.user_id = $user_id RETURN e.type as entity_type, COUNT(*) as count ORDER BY count DESC",
                            {"user_id": user_id},
                        )
                        memory_stats = kuzu.query(
                            "MATCH (m:Memory) WHERE m.user_id = $user_id RETURN m.memory_type as memory_type, COUNT(*) as count ORDER BY count DESC",
                            {"user_id": user_id},
                        )
                    else:
                        entity_stats = kuzu.query(
                            "MATCH (e:Entity) RETURN e.type as entity_type, COUNT(*) as count ORDER BY count DESC",
                            {},
                        )
                        memory_stats = kuzu.query(
                            "MATCH (m:Memory) RETURN m.memory_type as memory_type, COUNT(*) as count ORDER BY count DESC",
                            {},
                        )

                    schema_info["usage_statistics"] = {
                        "entity_type_distribution": entity_stats,
                        "memory_type_distribution": memory_stats,
                        "user_scoped": user_id is not None,
                    }
                except Exception as e:
                    schema_info["usage_statistics"] = {
                        "error": f"Could not retrieve stats: {str(e)}"
                    }

            schema_info["schema_metadata"] = {
                "version": "v0.4.0",
                "last_updated": "2025-01-16",
                "supports_user_isolation": True,
                "supports_project_scoping": True,
                "primary_search_engine": "qdrant",
                "relationship_engine": "kuzu",
            }

            return {
                "result": "✅ Memory schema retrieved successfully",
                "schema": schema_info,
            }

        except Exception as e:
            log_error("mcp_tools_core", "get_memory_schema", e, user_id=user_id)
            return {"result": f"❌ Failed to get memory schema: {str(e)}"}

    @app.tool("get_system_info")
    def get_system_info(random_string: str = "dummy"):
        """Get information about the memory system configuration."""
        memory = get_memory_system()
        if not memory:
            return {
                "result": {"components_initialized": False, "status": "Not initialized"}
            }

        try:
            stats = memory.get_stats()
            port = int(os.getenv("MEMORY_SYSTEM_MCP_PORT", "8787"))
            stats.update({"transport": "SSE", "port": port})
            return {"result": stats}

        except Exception as e:
            log_error("mcp_tools_core", "get_system_info", e)
            return {"result": f"❌ Failed to get system info: {str(e)}"}


def register_optional_tools(app: FastMCP) -> None:
    """Register optional tools based on environment flags"""

    # Optional generation tool (gated by env flag)
    if os.getenv("MEMG_ENABLE_GENERATION", "false").lower() == "true":

        @app.tool("generate_with_memory")
        def generate_with_memory(
            prompt: str,
            user_id: str,
            memory_limit: int = 5,
            system_instruction: str = "You are a helpful assistant that leverages relevant prior memories when useful.",
            temperature: float = 0.0,
            max_output_tokens: int = 2000,
        ):
            """Generate text using Gemini with optional memory context."""
            memory = get_memory_system()
            if not memory:
                return {"result": "❌ Memory system not initialized"}

            try:
                # Retrieve relevant memories
                retrieved = memory.search(
                    query=prompt, user_id=user_id, limit=max(1, memory_limit)
                )

                context_chunks = []
                used_ids = []
                for idx, item in enumerate(retrieved or []):
                    content = item.get("content") or ""
                    title = item.get("title") or None
                    memory_id = item.get("memory_id") or item.get("id")
                    used_ids.append(memory_id)
                    header = f"Memory {idx + 1}"
                    if title:
                        header += f" - {title}"
                    truncated = content[:2000]  # Truncate overly long memory content
                    context_chunks.append(f"{header}:\n{truncated}")

                context_block = (
                    "\n\n".join(context_chunks)
                    if context_chunks
                    else "(no relevant memories found)"
                )

                full_prompt = (
                    "You will answer the user's request. If memory context helps, use it; otherwise rely on general reasoning.\n\n"
                    f"Memory Context:\n{context_block}\n\n"
                    f"User Request:\n{prompt}\n\n"
                    "Instructions:\n- Be precise and actionable.\n- Cite steps or references from memory when relevant.\n"
                )

                genai_client = GenAI(system_instruction=system_instruction)
                generated = genai_client.generate_text(
                    content=full_prompt,
                    temperature=float(temperature),
                    max_output_tokens=int(max_output_tokens),
                )

                return {
                    "result": "✅ Generation completed",
                    "content": generated,
                    "used_memory_ids": used_ids,
                    "memory_count": len(used_ids),
                }

            except Exception as e:
                log_error("mcp_tools_core", "generate_with_memory", e)
                return {"result": f"❌ Failed to generate: {str(e)}"}
