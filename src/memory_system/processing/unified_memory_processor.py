"""
Unified Memory Processor - Optimized 2-call AI processing approach

Reduces AI calls from 4 to 2:
1. Unified Content Analysis (type + summary + themes + critical issues)
2. Focused Entity & Relationship Extraction (using analysis results)
"""

from datetime import UTC, datetime
import os
from typing import Any

from ..exceptions import ProcessingError, ValidationError
from ..kuzu_graph.interface import KuzuInterface
from ..logging_config import get_logger, log_error
from ..models import CreateMemoryRequest, Memory, MemoryType, ProcessingResponse
from ..models.template_models import TemplateAwareEntity as Entity
from ..models.template_models import (
    TemplateAwareRelationship,
    validate_entity_type,
    validate_relationship_type,
)
from ..qdrant.interface import QdrantInterface
from ..utils.embeddings import GenAIEmbedder
from ..utils.genai import GenAI
from ..utils.schemas import SCHEMAS
from ..utils.unified_schemas import get_unified_schemas
from ..validation import PipelineValidator

logger = get_logger("unified_memory_processor")


class UnifiedMemoryProcessor:
    """
    Optimized memory processor using 2-call approach:
    1. Unified content analysis
    2. Focused entity extraction
    """

    def __init__(
        self,
        qdrant: QdrantInterface | None = None,
        kuzu: KuzuInterface | None = None,
        embedder: GenAIEmbedder | None = None,
        validator: PipelineValidator | None = None,
        genai_client: GenAI | None = None,
    ):
        self.qdrant = qdrant or QdrantInterface()
        self.kuzu = kuzu or KuzuInterface()
        self.embedder = embedder or GenAIEmbedder()
        self.validator = validator or PipelineValidator()
        self.genai = genai_client or GenAI(
            system_instruction="You are an expert content analyst and entity extraction specialist."
        )

    def _get_timestamp_ms(self) -> int:
        """Get current timestamp in milliseconds"""
        return int(datetime.now(UTC).timestamp() * 1000)

    async def process_memory(
        self,
        request: CreateMemoryRequest,
    ) -> ProcessingResponse:
        """
        Process memory using optimized 2-call approach

        Args:
            request: Memory creation request

        Returns:
            ProcessingResponse with operation details
        """
        logger.info(f"Starting unified processing for content: {request.content[:100]}...")
        processing_start = self._get_timestamp_ms()

        try:
            # CALL 1: Unified Content Analysis (type + summary + themes + critical issues)
            content_analysis = await self._unified_content_analysis(request.content)

            # Extract results from analysis, but respect explicit TASK type
            ai_suggested_type = MemoryType(content_analysis["content_type"])
            if request.memory_type == MemoryType.TASK:
                # Always respect explicit TASK type - it's intentional from task management
                logger.info(
                    f"Preserving explicit TASK type (AI suggested: {ai_suggested_type.value})"
                )
                final_type = MemoryType.TASK
                # Generate task-specific summary if AI didn't provide one
                if not content_analysis["summary"] and ai_suggested_type != MemoryType.TASK:
                    summary = (
                        f"Task: {request.content[:100]}"
                        f"{'...' if len(request.content) > 100 else ''}"
                    )
                else:
                    summary = content_analysis["summary"] if content_analysis["summary"] else None
            else:
                final_type = ai_suggested_type
                summary = content_analysis["summary"] if content_analysis["summary"] else None

            # Generate embedding (fast, keep separate)
            embedding = self.embedder.get_embedding(request.content)

            # Create Memory object
            memory = Memory(
                user_id=request.user_id,
                content=request.content,
                memory_type=final_type,
                summary=summary,
                ai_verified_type=True,  # Always AI verified in unified approach
                title=request.title,
                tags=request.tags or [],
                project_id=request.project_id,
                source=request.source,
                created_at=datetime.now(UTC),
            )

            # Store in dual databases
            await self._store_memory_dual(memory, embedding)

            # CALL 2: Focused Entity & Relationship Extraction
            entities, relationships = [], []

            entity_extraction_enabled = (
                os.getenv("MEMG_ENABLE_ENTITY_EXTRACTION", "true").lower() == "true"
            )

            if entity_extraction_enabled and final_type in [
                MemoryType.DOCUMENT,
                MemoryType.NOTE,
            ]:
                entities, relationships = await self._focused_entity_extraction(
                    memory, content_analysis
                )
                logger.info(
                    f"Extracted {len(entities)} entities, {len(relationships)} relationships"
                )

                # Create MENTIONS relationships
                mentions_created = 0
                for entity in entities:
                    success = self.kuzu.add_relationship(
                        from_table="Memory",
                        to_table="Entity",
                        rel_type="MENTIONS",
                        from_id=memory.id,
                        to_id=entity.id,
                        props={
                            "user_id": memory.user_id,
                            "confidence": entity.confidence,
                            "created_at": memory.created_at.isoformat(),
                        },
                    )
                    if success:
                        mentions_created += 1

                logger.info(f"Created {mentions_created} MENTIONS relationships")

                # Update Qdrant payload with extracted entity types for filtering
                try:
                    if entities:
                        unique_entity_types = []
                        for entity in entities:
                            entity_type_value = getattr(entity, "type", None)
                            if not entity_type_value:
                                continue
                            # Normalize to uppercase string values
                            normalized = (
                                entity_type_value.value
                                if hasattr(entity_type_value, "value")
                                else str(entity_type_value)
                            ).upper()
                            if normalized not in unique_entity_types:
                                unique_entity_types.append(normalized)

                        if unique_entity_types:
                            updated_payload = memory.to_qdrant_payload()
                            updated_payload["entity_types"] = unique_entity_types
                            success = self.qdrant.update_point_payload(
                                point_id=memory.id, payload=updated_payload
                            )
                            if success:
                                logger.info(
                                    f"Updated Qdrant payload with entity types: "
                                    f"{unique_entity_types}"
                                )
                            else:
                                logger.warning("Failed to update Qdrant payload with entity types")
                except Exception as e:
                    logger.warning(
                        f"Failed to push entity_types to Qdrant payload for {memory.id}: {e}"
                    )

            # Calculate processing time
            processing_end = self._get_timestamp_ms()
            processing_time = processing_end - processing_start

            logger.info(f"Unified processing completed successfully: {memory.id}")

            return ProcessingResponse(
                success=True,
                memory_id=memory.id,
                final_type=final_type,
                ai_verified=True,
                summary_generated=bool(summary),
                type_changed=(
                    request.memory_type is not None and final_type != request.memory_type
                ),
                processing_time_ms=processing_time,
                word_count=len(request.content.split()),
                entities_extracted=len(entities),
                relationships_created=len(relationships),
            )

        except Exception as e:
            processing_end = self._get_timestamp_ms()
            processing_time = processing_end - processing_start

            log_error("unified_memory_processor", "process_memory", e)

            return ProcessingResponse(
                success=False,
                memory_id="",
                final_type=MemoryType.NOTE,
                ai_verified=False,
                summary_generated=False,
                type_changed=False,
                error=str(e),
                processing_time_ms=processing_time,
                word_count=len(request.content.split()),
                entities_extracted=0,
                relationships_created=0,
            )

    async def _unified_content_analysis(self, content: str) -> dict[str, Any]:
        """
        CALL 1: Unified content analysis - type, summary, themes, critical issues

        Args:
            content: Content to analyze

        Returns:
            Dictionary with analysis results
        """
        try:
            # Load unified analysis prompt

            prompt_path = os.path.join(
                os.path.dirname(__file__),
                "..",
                "prompts",
                "unified_analysis",
                "content_analysis.md",
            )
            with open(prompt_path, encoding="utf-8") as f:
                system_prompt = f.read()

            genai_client = GenAI(system_instruction=system_prompt)

            # Get unified schema
            unified_schemas = get_unified_schemas()
            schema_dict = unified_schemas["unified_content_analysis"]

            # Prepare input (limit for performance)
            limited_content = content[:2000] if len(content) > 2000 else content

            input_text = f"""
Analyze this content comprehensively:

CONTENT:
{limited_content}

WORD COUNT: {len(content.split())}

Provide complete analysis following the schema.
"""

            # Generate unified analysis
            analysis_result = genai_client.generate_json(
                content=input_text, json_schema=schema_dict
            )

            logger.debug(f"Unified content analysis result: {analysis_result}")
            return analysis_result

        except Exception as e:
            log_error("unified_memory_processor", "unified_content_analysis", e)
            # Fallback to basic analysis
            return {
                "content_type": "note",
                "summary": "",
                "key_themes": ["general_content"],
                "content_complexity": "SIMPLE",
                "domain": "general",
                "priority_entities": [],
                "critical_issues": [],
            }

    async def _focused_entity_extraction(
        self, memory: Memory, content_analysis: dict[str, Any]
    ) -> tuple[list[Entity], list]:
        """
        CALL 2: Focused entity extraction using content analysis results

        Args:
            memory: Memory object
            content_analysis: Results from unified content analysis

        Returns:
            Tuple of (entities, relationships)
        """
        try:
            # Create focused extraction prompt using analysis results
            themes = ", ".join(content_analysis.get("key_themes", []))
            priority_entities = ", ".join(content_analysis.get("priority_entities", []))
            critical_issues = content_analysis.get("critical_issues", [])

            focused_prompt = f"""
You are an expert entity extraction specialist. Extract entities and \
        relationships from the given content.

CONTENT ANALYSIS CONTEXT:
- Domain: {content_analysis.get("domain", "general")}
- Key Themes: {themes}
- Priority Entities: {priority_entities}
- Critical Issues Identified: {len(critical_issues)} issues
- Content Complexity: {content_analysis.get("content_complexity", "SIMPLE")}

Focus your extraction on:
1. The identified key themes and priority entities
2. Critical issues (vulnerabilities, conflicts, performance problems)
3. Relationships between technical components
4. Problem-solution connections

Use the template entity types and prioritize critical issue types:
VULNERABILITY, CONFLICT, PERFORMANCE, ERROR, DEPRECATION, SOLUTION
"""

            genai_client = GenAI(system_instruction=focused_prompt)

            # Get entity extraction schema
            schema_dict = SCHEMAS["entity_relationship_extraction"]

            # Prepare focused input
            input_text = f"""
Memory Content: {memory.content}
Memory Title: {memory.title or "N/A"}
Memory Type: {memory.memory_type.value}

EXTRACTION FOCUS:
- Key Themes: {themes}
- Priority Entities: {priority_entities}
- Critical Issues to Extract: {[issue.get("description", "") for issue in critical_issues]}

Extract entities and relationships with focus on the above context.
"""

            # Generate focused extraction
            extraction_result = genai_client.generate_json(
                content=input_text, json_schema=schema_dict
            )

            logger.debug(f"Focused entity extraction result: {extraction_result}")

            # Process entities and relationships (same as original processor)
            entities = []
            entity_name_to_id = {}

            for entity_data in extraction_result.get("entities", []):
                try:
                    entity_type_str = entity_data["type"]
                    if not validate_entity_type(entity_type_str):
                        logger.warning(
                            f"Skipping entity with invalid type '{entity_type_str}': "
                            f"{entity_data.get('name')}"
                        )
                        continue

                    entity = Entity(
                        user_id=memory.user_id,
                        name=entity_data["name"],
                        type=entity_type_str,
                        description=entity_data["description"],
                        confidence=entity_data["confidence"],
                        importance=entity_data.get("importance", "MEDIUM"),
                        context=entity_data.get("context", ""),
                        source_memory_id=memory.id,
                    )

                    # Store entity in Kuzu
                    success = self.kuzu.add_node("Entity", entity.to_kuzu_node())
                    if success:
                        entities.append(entity)
                        entity_name_to_id[entity.name] = entity.id
                        logger.debug(f"Stored entity: {entity.name} (ID: {entity.id})")

                except (ValueError, ValidationError) as e:
                    logger.warning(
                        f"Skipping entity due to validation error: {entity_data.get('name')} - {e}"
                    )
                    continue

            # Process relationships
            relationships = []
            for rel_data in extraction_result.get("relationships", []):
                source_name = rel_data["source"]
                target_name = rel_data["target"]

                source_id = entity_name_to_id.get(source_name)
                target_id = entity_name_to_id.get(target_name)

                if source_id and target_id:
                    rel_type_str = rel_data["type"]
                    if not validate_relationship_type(rel_type_str):
                        logger.warning(
                            f"Skipping relationship with invalid type '{rel_type_str}': "
                            f"{source_name} -> {target_name}"
                        )
                        continue

                    relationship = TemplateAwareRelationship(
                        user_id=memory.user_id,
                        source_entity_id=source_id,
                        target_entity_id=target_id,
                        type=rel_type_str,
                        confidence=rel_data["confidence"],
                        strength=rel_data.get("strength", "MODERATE"),
                        context=rel_data.get("context", ""),
                        source_memory_id=memory.id,
                    )

                    # Store relationship in Kuzu
                    success = self.kuzu.add_relationship(
                        from_table="Entity",
                        to_table="Entity",
                        rel_type=relationship.type,
                        from_id=relationship.source_entity_id,
                        to_id=relationship.target_entity_id,
                        props=relationship.to_kuzu_props(),
                    )
                    if success:
                        relationships.append(relationship)
                        logger.debug(f"Stored relationship: {source_name} -> {target_name}")
                else:
                    logger.warning(
                        f"Skipping relationship {source_name} -> {target_name}: entity not found"
                    )

            return entities, relationships

        except Exception as e:
            log_error("unified_memory_processor", "focused_entity_extraction", e)
            return [], []

    async def _store_memory_dual(self, memory: Memory, embedding: list[float]) -> None:
        """Store memory in both Qdrant and Kuzu"""
        try:
            # Store in Qdrant
            memory_payload = {
                "user_id": memory.user_id,
                "content": memory.content,
                "memory_type": memory.memory_type.value,
                "title": memory.title or "",
                "tags": memory.tags,
                "project_id": memory.project_id or "",
                "source": memory.source or "",
                "summary": memory.summary or "",
                "created_at": memory.created_at.isoformat(),
                "is_valid": memory.is_valid,
                "confidence": memory.confidence,
            }
            success, _ = self.qdrant.add_point(
                vector=embedding, payload=memory_payload, point_id=memory.id
            )
            if not success:
                raise ProcessingError(
                    "Qdrant upsert was not acknowledged",
                    operation="store_memory_dual",
                    original_error=None,
                )
            logger.debug(f"Stored memory in Qdrant: {memory.id}")

            # Store in Kuzu
            memory_props = {
                "id": memory.id,
                "user_id": memory.user_id,
                "project_id": memory.project_id or "",
                "project_name": memory.project_name or "",
                "content": memory.content,
                "memory_type": memory.memory_type.value,
                "summary": memory.summary or "",
                "title": memory.title or "",
                "source": memory.source or "",
                "tags": ",".join(memory.tags) if memory.tags else "",
                "confidence": memory.confidence,
                "is_valid": memory.is_valid,
                "created_at": memory.created_at.isoformat(),
                "expires_at": (memory.expires_at.isoformat() if memory.expires_at else ""),
            }

            success = self.kuzu.add_node("Memory", memory_props)
            if success:
                logger.debug(f"Stored memory in Kuzu: {memory.id}")
            else:
                logger.error(f"Failed to store memory in Kuzu: {memory.id}")

        except Exception as e:
            log_error("unified_memory_processor", "store_memory_dual", e)
            raise ProcessingError(
                "Failed to store memory in dual databases",
                operation="store_memory_dual",
                original_error=e,
            )
