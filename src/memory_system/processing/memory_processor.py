"""
Core Memory Processor - Simplified g^mem processing pipeline.

This module handles the end-to-end processing for documents and notes:
1. AI-based type detection and verification
2. Document summary generation (1000 token limit)
3. Embedding generation and dual storage
4. Simple, fast processing focused on documents and notes
"""

import os

from ..exceptions import NetworkError, ProcessingError, ValidationError
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
from ..validation import PipelineValidator

logger = get_logger("memory_processor")


class MemoryProcessor:
    """
    Simplified memory processing orchestrator for g^mem.

    Handles the streamlined pipeline:
    1. AI-based type detection and verification
    2. Document summary generation (for documents only)
    3. Embedding generation
    4. Dual storage (Qdrant + Kuzu)
    5. Processing response generation
    """

    def __init__(
        self,
        qdrant_interface: QdrantInterface | None = None,
        kuzu_interface: KuzuInterface | None = None,
        genai_client: GenAI | None = None,
        embedder: GenAIEmbedder | None = None,
    ):
        """
        Initialize the Memory Processor with required interfaces.

        Args:
            qdrant_interface: Qdrant vector database interface
            kuzu_interface: Kuzu graph database interface
            genai_client: GenAI client for AI operations
            embedder: Embedding generator for vectors
        """
        self.qdrant = qdrant_interface or QdrantInterface()
        self.kuzu = kuzu_interface or KuzuInterface()
        self.genai = genai_client or GenAI(
            system_instruction="You are a memory processing assistant."
        )
        self.embedder = embedder or GenAIEmbedder()
        self.validator = PipelineValidator()

        logger.info("MemoryProcessor initialized for simplified g^mem processing")

    async def process_memory(
        self,
        request: CreateMemoryRequest,
    ) -> ProcessingResponse:
        """
        Process a memory creation request through the simplified pipeline.

        Args:
            request: Memory creation request

        Returns:
            ProcessingResponse with operation details and success status
        """
        logger.info(f"Starting g^mem processing for content: {request.content[:100]}...")
        processing_start = self._get_timestamp_ms()

        try:
            # Step 1: AI-based type detection and verification
            (
                final_type,
                ai_verified,
                type_changed,
                original_type,
            ) = await self._detect_and_verify_type(
                content=request.content, suggested_type=request.memory_type
            )

            # Step 2: Generate summary for documents (if needed)
            summary = None
            summary_generated = False
            if final_type == MemoryType.DOCUMENT:
                summary = await self._generate_document_summary(request.content)
                summary_generated = True

            # Step 3: Create Memory object with embeddings
            memory = await self._create_memory_object(
                request=request,
                final_type=final_type,
                summary=summary,
                ai_verified=ai_verified,
            )

            # Step 4: Store in dual databases
            await self._store_memory_dual(memory)

            # Step 4.5: Extract entities and relationships (NEW)
            entities, relationships = [], []

            entity_extraction_enabled = (
                os.getenv("MEMG_ENABLE_ENTITY_EXTRACTION", "true").lower() == "true"
            )

            if entity_extraction_enabled and final_type in [
                MemoryType.DOCUMENT,
                MemoryType.NOTE,
            ]:
                try:
                    (
                        entities,
                        relationships,
                    ) = await self._extract_entities_and_relationships(memory)
                    logger.info(
                        f"Extracted {len(entities)} entities, {len(relationships)} relationships"
                    )

                    # Create MENTIONS relationships from Memory to each Entity
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

                    # Step 4.6: Update Qdrant payload with extracted entity types for filtering
                    if entities:
                        entity_types = list(set([entity.type.value for entity in entities]))

                        # Update the Qdrant point with entity_types field
                        updated_payload = memory.to_qdrant_payload()
                        updated_payload["entity_types"] = entity_types

                        success = self.qdrant.update_point_payload(
                            point_id=memory.id, payload=updated_payload
                        )

                        if success:
                            logger.info(f"Updated Qdrant payload with entity types: {entity_types}")
                        else:
                            logger.warning("Failed to update Qdrant payload with entity types")

                except Exception as e:
                    logger.warning(f"Entity extraction failed, continuing without: {e}")
                    # Continue processing - don't fail memory creation

            # Step 5: Generate processing response
            processing_time = self._get_timestamp_ms() - processing_start

            result = ProcessingResponse(
                success=True,
                memory_id=memory.id,
                final_type=final_type,
                ai_verified=ai_verified,
                summary_generated=summary_generated,
                processing_time_ms=processing_time,
                type_changed=type_changed,
                original_type=original_type,
                word_count=memory.word_count(),
            )

            logger.info(f"g^mem processing completed successfully: {memory.id}")
            return result

        except (ValidationError, ValueError) as e:
            processing_time = self._get_timestamp_ms() - processing_start
            log_error(
                "memory_processor",
                "process_memory",
                e,
                content_length=len(request.content),
                processing_time_ms=processing_time,
            )
            return ProcessingResponse(
                success=False,
                memory_id="",
                final_type=request.memory_type or MemoryType.NOTE,
                ai_verified=False,
                summary_generated=False,
                processing_time_ms=processing_time,
                word_count=len(request.content.split()),
            )
        except (NetworkError, ConnectionError, TimeoutError) as e:
            processing_time = self._get_timestamp_ms() - processing_start
            log_error(
                "memory_processor",
                "process_memory",
                e,
                content_length=len(request.content),
                processing_time_ms=processing_time,
            )
            return ProcessingResponse(
                success=False,
                memory_id="",
                final_type=request.memory_type or MemoryType.NOTE,
                ai_verified=False,
                summary_generated=False,
                processing_time_ms=processing_time,
                word_count=len(request.content.split()),
            )
        except Exception as e:
            processing_time = self._get_timestamp_ms() - processing_start
            log_error(
                "memory_processor",
                "process_memory",
                e,
                content_length=len(request.content),
                processing_time_ms=processing_time,
            )

            # Return failure response
            return ProcessingResponse(
                success=False,
                memory_id="",
                final_type=request.memory_type or MemoryType.NOTE,
                ai_verified=False,
                summary_generated=False,
                processing_time_ms=processing_time,
                word_count=len(request.content.split()),
            )

    async def _detect_and_verify_type(
        self, content: str, suggested_type: MemoryType | None
    ) -> tuple[MemoryType, bool, bool, MemoryType | None]:
        """
        AI-based type detection and verification with word count heuristics.

        Args:
            content: Content to analyze
            suggested_type: User-suggested type (optional)

        Returns:
            Tuple of (final_type, ai_verified, type_changed, original_type)
        """
        try:
            word_count = len(content.split())

            # Simple heuristic first: very short content is always a note
            if word_count <= 5:
                return MemoryType.NOTE, True, False, suggested_type

            # Use AI for type detection and verification
            ai_type = await self._ai_type_detection(content, word_count)

            if suggested_type is None:
                # No suggestion, use AI detection
                return ai_type, True, False, None

            if suggested_type == ai_type:
                # Suggestion matches AI, all good
                return ai_type, True, False, None

            if suggested_type == MemoryType.TASK:
                # Always respect explicit TASK type - it's intentional from task management
                logger.info(f"Preserving explicit TASK type (AI suggested: {ai_type.value})")
                return MemoryType.TASK, True, False, None
            # AI disagrees with suggestion, use AI decision
            logger.info(f"Type correction: {suggested_type.value} -> {ai_type.value}")
            return ai_type, True, True, suggested_type

        except (NetworkError, ConnectionError, TimeoutError) as e:
            log_error(
                "memory_processor",
                "type_detection",
                e,
                content_length=len(content),
                word_count=word_count,
            )
            return suggested_type or MemoryType.NOTE, False, False, None
        except (ValidationError, ValueError) as e:
            log_error(
                "memory_processor",
                "type_detection",
                e,
                content_length=len(content),
                word_count=word_count,
            )
            return suggested_type or MemoryType.NOTE, False, False, None
        except Exception as e:
            log_error(
                "memory_processor",
                "type_detection",
                e,
                content_length=len(content),
                word_count=word_count,
            )
            return suggested_type or MemoryType.NOTE, False, False, None

    async def _ai_type_detection(self, content: str, word_count: int) -> MemoryType:
        """
        Use AI to detect memory type based on content analysis.

        Args:
            content: Content to analyze
            word_count: Pre-calculated word count

        Returns:
            Detected MemoryType
        """
        # Apply word count thresholds first
        if word_count < 30:
            # Very short content: likely a note unless clearly documentation or task
            if any(
                keyword in content.lower()
                for keyword in [
                    "documentation",
                    "specification",
                    "tutorial",
                    "api reference",
                ]
            ):
                return MemoryType.DOCUMENT
            if any(
                keyword in content.lower()
                for keyword in [
                    "task",
                    "ticket",
                    "story",
                    "epic",
                    "sprint",
                    "implement",
                    "fix",
                    "create",
                    "build",
                    "develop",
                    "due date",
                    "assignee",
                    "priority",
                ]
            ):
                return MemoryType.TASK
            return MemoryType.NOTE

        if word_count > 200:
            # Long content: likely a document unless clearly a brief record
            if any(
                keyword in content.lower()
                for keyword in [
                    "user prefers",
                    "team decided",
                    "team agreed",
                    "meeting outcome",
                    "user said",
                ]
            ):
                return MemoryType.NOTE
            return MemoryType.DOCUMENT

        # Medium content: use AI to decide
        from ..utils.prompts import prompt_loader

        system_prompt = prompt_loader.get_memory_type_classification_prompt()

        try:
            genai_client = GenAI(system_instruction=system_prompt)
            response = genai_client.generate_text(
                content=f"Classify this content (word count: {word_count}):\n\n"
                f"{content[:1000]}"  # Limit for latency
            )

            response_lower = response.strip().lower()
            if "task" in response_lower:
                return MemoryType.TASK
            if "document" in response_lower:
                return MemoryType.DOCUMENT
            return MemoryType.NOTE

        except (NetworkError, ConnectionError, TimeoutError) as e:
            log_error(
                "memory_processor",
                "ai_type_detection",
                e,
                content_length=len(content),
                word_count=word_count,
            )
            # Fallback to word count heuristic for network issues
            return MemoryType.DOCUMENT if word_count > 200 else MemoryType.NOTE
        except (ValidationError, ValueError) as e:
            log_error(
                "memory_processor",
                "ai_type_detection",
                e,
                content_length=len(content),
                word_count=word_count,
            )
            # Fallback to word count heuristic for validation issues
            return MemoryType.DOCUMENT if word_count > 200 else MemoryType.NOTE
        except Exception as e:
            log_error(
                "memory_processor",
                "ai_type_detection",
                e,
                content_length=len(content),
                word_count=word_count,
            )
            # Fallback to word count heuristic
            return MemoryType.DOCUMENT if word_count > 200 else MemoryType.NOTE

    async def _generate_document_summary(self, content: str) -> str:
        """
        Generate AI summary for document content (1000 token limit for latency).

        Args:
            content: Document content to summarize

        Returns:
            Generated summary string
        """
        try:
            # Limit content to first 1000 tokens (roughly 750-800 words) for latency
            limited_content = " ".join(content.split()[:750])

            from ..utils.prompts import prompt_loader

            system_prompt = prompt_loader.get_document_summarization_prompt()

            genai_client = GenAI(system_instruction=system_prompt)
            summary = genai_client.generate_text(
                content=f"Summarize this document:\n\n{limited_content}"
            )

            logger.debug(f"Generated summary: {summary[:100]}...")
            return summary.strip()

        except (NetworkError, ConnectionError, TimeoutError) as e:
            log_error("memory_processor", "summary_generation", e, content_length=len(content))
            # Fallback to simple truncation for network issues
            return content[:200] + "..." if len(content) > 200 else content
        except (ValidationError, ValueError) as e:
            log_error("memory_processor", "summary_generation", e, content_length=len(content))
            # Fallback to simple truncation for validation issues
            return content[:200] + "..." if len(content) > 200 else content
        except Exception as e:
            log_error("memory_processor", "summary_generation", e, content_length=len(content))
            # Fallback to simple truncation
            return content[:200] + "..." if len(content) > 200 else content

    async def _create_memory_object(
        self,
        request: CreateMemoryRequest,
        final_type: MemoryType,
        summary: str | None,
        ai_verified: bool,
    ) -> Memory:
        """
        Create Memory object with embeddings.

        Args:
            request: Original request
            final_type: Final determined type
            summary: Generated summary (for documents)
            ai_verified: Whether AI verified the type

        Returns:
            Complete Memory object
        """
        # Generate embedding
        embedding = self.embedder.get_embedding(request.content)

        # Create Memory object
        memory = Memory(
            user_id=request.user_id,
            content=request.content,
            memory_type=final_type,
            summary=summary,
            ai_verified_type=ai_verified,
            title=request.title,
            source=request.source,
            tags=request.tags,
            confidence=request.confidence,
            vector=embedding,
            project_id=request.project_id,
            project_name=request.project_name,
        )

        logger.debug(f"Created memory object: {memory.id[:8]}... (type: {final_type.value})")
        return memory

    async def _store_memory_dual(self, memory: Memory) -> bool:
        """
        Store memory in both Qdrant and Kuzu databases.

        Args:
            memory: Memory object to store

        Returns:
            True if successful
        """
        # Store in Qdrant for semantic search
        qdrant_success = self.qdrant.add_point(
            vector=memory.vector,
            payload=memory.to_qdrant_payload(),
            point_id=memory.id,
        )

        if not qdrant_success:
            raise RuntimeError(f"Failed to store memory {memory.id} in Qdrant")

        # Store in Kuzu for graph relationships
        kuzu_props = memory.to_kuzu_node()
        kuzu_success = self.kuzu.add_node("Memory", kuzu_props)

        if not kuzu_success:
            raise RuntimeError(f"Failed to store memory {memory.id} in Kuzu")

        logger.debug(f"Successfully stored memory {memory.id} in both databases")
        return True

    def _get_timestamp_ms(self) -> float:
        """Get current timestamp in milliseconds"""
        import time

        return time.time() * 1000

    async def invalidate_memory(
        self,
        memory_id: str,
        invalidated_by: str | None = None,
        reason: str | None = None,
    ) -> bool:
        """
        Mark a memory as invalid instead of deleting it (temporal reasoning).

        Args:
            memory_id: ID of memory to invalidate
            invalidated_by: ID of the memory that caused this invalidation
            reason: Reason for invalidation

        Returns:
            True if successfully invalidated
        """
        try:
            # Note: This is a simplified implementation
            # In a full implementation, we would:
            # 1. Retrieve the memory from Qdrant
            # 2. Update its metadata to mark as invalid
            # 3. Update both Qdrant and Kuzu records

            logger.info(f"Invalidating memory {memory_id} - reason: {reason}")

            # For now, we'll just log the invalidation
            # TODO: Implement actual memory retrieval and update
            # This requires enhancing QdrantInterface with update_point method

            return True

        except (NetworkError, ConnectionError, TimeoutError) as e:
            log_error("memory_processor", "invalidate_memory", e, memory_id=memory_id)
            return False
        except (ValidationError, ValueError) as e:
            log_error("memory_processor", "invalidate_memory", e, memory_id=memory_id)
            return False
        except Exception as e:
            log_error("memory_processor", "invalidate_memory", e, memory_id=memory_id)
            return False

    async def invalidate_conflicting_memories(
        self, new_memory: Memory, conflict_ids: list[str]
    ) -> int:
        """
        Invalidate memories that conflict with a new memory.

        Args:
            new_memory: The new memory that caused conflicts
            conflict_ids: List of memory IDs that conflict

        Returns:
            Number of memories successfully invalidated
        """
        invalidated_count = 0

        for conflict_id in conflict_ids:
            success = await self.invalidate_memory(
                memory_id=conflict_id,
                invalidated_by=new_memory.id,
                reason="Superseded by new information",
            )
            if success:
                invalidated_count += 1

        if invalidated_count > 0:
            logger.info(
                f"Invalidated {invalidated_count} conflicting memories "
                f"due to new memory: {new_memory.content[:50]}..."
            )

        return invalidated_count

    def get_valid_memories_only(self) -> bool:
        """
        Get configuration for whether to return only valid memories in searches.

        Returns:
            True if only valid memories should be returned
        """
        from ..config import get_config

        config = get_config()
        return config.memg.enable_temporal_reasoning

    async def _extract_entities_and_relationships(self, memory: Memory) -> tuple[list, list]:
        """
        Extract entities and relationships from a memory using GenAI.

        Args:
            memory: Memory object to extract from

        Returns:
            Tuple of (extracted_entities, extracted_relationships)
        """
        try:
            # Get system prompt for entity/relationship extraction
            from ..utils.prompts import prompt_loader

            system_prompt = prompt_loader.get_entity_extraction_prompt()

            # Use GenAI with structured output
            genai_client = GenAI(system_instruction=system_prompt)

            # Get the schema for entity/relationship extraction (direct dict, no JSON conversion)
            schema_dict = SCHEMAS["entity_relationship_extraction"]

            # Prepare input
            input_text = f"""
Memory Content: {memory.content}
Memory Title: {memory.title or "N/A"}
Memory Type: {memory.memory_type.value}
Memory Tags: {", ".join(memory.tags) if memory.tags else "N/A"}

Extract entities and relationships from this memory content.
"""

            # Generate structured extraction
            extraction_result = genai_client.generate_json(
                content=input_text, json_schema=schema_dict
            )

            logger.debug(f"GenAI entity/relationship extraction result: {extraction_result}")

            # Convert and store entities
            entities = []
            entity_name_to_id = {}  # Map entity names to UUIDs for relationship creation

            for entity_data in extraction_result.get("entities", []):
                try:
                    # Validate entity type against current template
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
                        type=entity_type_str,  # Use string directly, validation handled by model
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
                        entity_name_to_id[entity.name] = entity.id  # Map name to UUID
                        logger.debug(f"Stored entity: {entity.name} (ID: {entity.id})")
                except (ValueError, ValidationError) as e:
                    logger.warning(
                        f"Skipping entity due to validation error: {entity_data.get('name')} - {e}"
                    )
                    continue

            # Convert and store relationships between entities
            relationships = []
            for rel_data in extraction_result.get("relationships", []):
                source_name = rel_data["source"]
                target_name = rel_data["target"]

                # Map entity names to actual UUIDs
                source_id = entity_name_to_id.get(source_name)
                target_id = entity_name_to_id.get(target_name)

                if source_id and target_id:
                    # Validate relationship type against current template
                    rel_type_str = rel_data["type"]
                    if not validate_relationship_type(rel_type_str):
                        logger.warning(
                            f"Skipping relationship with invalid type '{rel_type_str}': "
                            f"{source_name} -> {target_name}"
                        )
                        continue

                    relationship = TemplateAwareRelationship(
                        user_id=memory.user_id,
                        source_entity_id=source_id,  # Use actual UUID
                        target_entity_id=target_id,  # Use actual UUID
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
                        logger.debug(
                            f"Stored relationship: {source_name} -> {target_name} "
                            f"(UUIDs: {source_id[:8]}...-> {target_id[:8]}...)"
                        )
                else:
                    logger.warning(
                        f"Skipping relationship {source_name} -> {target_name}: entity not found"
                    )

            return entities, relationships

        except (NetworkError, ConnectionError, TimeoutError) as e:
            log_error("memory_processor", "entity_relationship_extraction", e)
            raise ProcessingError(
                "Network error during entity/relationship extraction",
                operation="entity_relationship_extraction",
                original_error=e,
            )
        except (ValidationError, ValueError) as e:
            log_error("memory_processor", "entity_relationship_extraction", e)
            raise ProcessingError(
                "Validation error during entity/relationship extraction",
                operation="entity_relationship_extraction",
                original_error=e,
            )
        except Exception as e:
            log_error("memory_processor", "entity_relationship_extraction", e)
            raise ProcessingError(
                "CRITICAL: Entity/relationship extraction failed",
                operation="entity_relationship_extraction",
                original_error=e,
            )
