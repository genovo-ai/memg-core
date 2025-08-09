"""
Standalone Schema Validation Tool

This is a non-invasive validation tool that can be used to validate
the memory processing pipeline without modifying existing code.

Usage:
    from memory_system.validation import standalone_validator
    validator = standalone_validator.create_validator()
    report = validator.validate_memory_flow(...)
"""

import logging
import os
from typing import Any, Dict, List, Optional

from ..models import Entity, Memory, Relationship
from .pipeline_validator import PipelineValidationReport, PipelineValidator

logger = logging.getLogger(__name__)


class StandaloneValidator:
    """
    Standalone validator that can validate memory processing without
    modifying existing committed code.
    """

    def __init__(self):
        self.pipeline_validator = PipelineValidator()
        logger.info("StandaloneValidator initialized")

    def validate_ai_outputs(
        self,
        content_analysis_output: Dict[str, Any],
        memory_extraction_output: Dict[str, Any],
        entity_extraction_output: Optional[Dict[str, Any]] = None,
    ) -> PipelineValidationReport:
        """
        Validate raw AI outputs against schemas.

        Args:
            content_analysis_output: Raw output from content analysis AI
            memory_extraction_output: Raw output from memory extraction AI
            entity_extraction_output: Raw output from entity extraction AI (optional)

        Returns:
            Validation report with schema compliance issues
        """
        report = PipelineValidationReport(
            pipeline_valid=True, total_issues=0, error_count=0, warning_count=0
        )

        # Validate content analysis
        content_result = self.pipeline_validator.schema_validator.validate_ai_output(
            content_analysis_output, "content_analysis"
        )
        report.add_validation_result(content_result)

        # Validate memory extraction
        extraction_result = self.pipeline_validator.schema_validator.validate_ai_output(
            memory_extraction_output, "memory_extraction"
        )
        report.add_validation_result(extraction_result)

        # Validate entity extraction if provided
        if entity_extraction_output:
            entity_result = self.pipeline_validator.schema_validator.validate_ai_output(
                entity_extraction_output, "entity_relationship_extraction"
            )
            report.add_validation_result(entity_result)

        return report

    def validate_memory_objects(
        self,
        memories: List[Memory],
        entities: Optional[List[Entity]] = None,
        relationships: Optional[List[Relationship]] = None,
    ) -> PipelineValidationReport:
        """
        Validate Memory, Entity, and Relationship objects for database compatibility.

        Args:
            memories: List of Memory objects to validate
            entities: List of Entity objects to validate (optional)
            relationships: List of Relationship objects to validate (optional)

        Returns:
            Validation report with database compatibility issues
        """
        report = PipelineValidationReport(
            pipeline_valid=True, total_issues=0, error_count=0, warning_count=0
        )

        # Validate memories
        for i, memory in enumerate(memories):
            qdrant_result = (
                self.pipeline_validator.schema_validator.validate_database_compatibility(
                    memory, "qdrant"
                )
            )
            qdrant_result.component = f"Memory {i+1} (Qdrant)"
            report.add_validation_result(qdrant_result)

            kuzu_result = self.pipeline_validator.schema_validator.validate_database_compatibility(
                memory, "kuzu"
            )
            kuzu_result.component = f"Memory {i+1} (Kuzu)"
            report.add_validation_result(kuzu_result)

        # Validate entities if provided
        if entities:
            for i, entity in enumerate(entities):
                entity_result = (
                    self.pipeline_validator.schema_validator.validate_database_compatibility(
                        entity, "kuzu"
                    )
                )
                entity_result.component = f"Entity {i+1} ({entity.name})"
                report.add_validation_result(entity_result)

        # Validate relationships if provided
        if relationships:
            for i, relationship in enumerate(relationships):
                rel_data = relationship.to_kuzu_props()
                rel_result = self.pipeline_validator.schema_validator.validate_relationship_schema(
                    rel_data
                )
                rel_result.component = f"Relationship {i+1} ({relationship.relationship_type})"
                report.add_validation_result(rel_result)

        return report

    def validate_complete_flow(
        self,
        original_content: str,
        ai_content_analysis: Dict[str, Any],
        ai_memory_extraction: Dict[str, Any],
        final_memories: List[Memory],
        ai_entity_extraction: Optional[Dict[str, Any]] = None,
        extracted_entities: Optional[List[Entity]] = None,
        extracted_relationships: Optional[List[Relationship]] = None,
    ) -> PipelineValidationReport:
        """
        Validate the complete memory processing flow end-to-end.

        This is the main validation method that checks everything from
        AI outputs to final database objects.

        Args:
            original_content: The original input content
            ai_content_analysis: Raw AI content analysis output
            ai_memory_extraction: Raw AI memory extraction output
            final_memories: Final Memory objects created
            ai_entity_extraction: Raw AI entity extraction output (optional)
            extracted_entities: Final Entity objects (optional)
            extracted_relationships: Final Relationship objects (optional)

        Returns:
            Complete validation report
        """
        logger.info("Starting complete flow validation")

        # Use the pipeline validator's main method
        return self.pipeline_validator.validate_memory_creation_flow(
            content=original_content,
            ai_analysis=ai_content_analysis,
            ai_extraction=ai_memory_extraction,
            final_memories=final_memories,
        )

    def print_report(self, report: PipelineValidationReport):
        """Print a formatted validation report."""
        self.pipeline_validator.print_validation_report(report)

    def quick_validate_memory(self, memory: Memory) -> bool:
        """
        Quick validation check for a single Memory object.

        Args:
            memory: Memory object to validate

        Returns:
            True if memory passes basic validation, False otherwise
        """
        # Check basic requirements
        if not memory.content or not memory.content.strip():
            return False

        if memory.vector is None or len(memory.vector) == 0:
            return False

        # Get expected dimension from environment
        expected_dim = int(os.getenv("EMBEDDING_DIMENSION_LEN", "768"))
        if len(memory.vector) != expected_dim:  # Embedding dimension from env
            return False

        if not all(isinstance(x, (int, float)) for x in memory.vector):
            return False

        return True


def create_validator() -> StandaloneValidator:
    """
    Factory function to create a StandaloneValidator instance.

    Returns:
        Configured StandaloneValidator ready for use
    """
    return StandaloneValidator()


# Convenience functions for common validation tasks
def validate_ai_output(output: Dict[str, Any], schema_name: str) -> bool:
    """
    Quick validation of AI output against schema.

    Args:
        output: AI output dictionary
        schema_name: Name of schema to validate against

    Returns:
        True if valid, False if issues found
    """
    validator = create_validator()
    result = validator.pipeline_validator.schema_validator.validate_ai_output(output, schema_name)
    return result.is_valid


def validate_memory_list(memories: List[Memory]) -> bool:
    """
    Quick validation of a list of Memory objects.

    Args:
        memories: List of Memory objects

    Returns:
        True if all memories are valid, False otherwise
    """
    validator = create_validator()
    return all(validator.quick_validate_memory(memory) for memory in memories)


def run_validation_demo():
    """
    Demo function showing how to use the validation system.
    """
    print("🔍 Schema Validation System Demo")
    print("=" * 50)

    validator = create_validator()

    # Example AI output validation
    sample_ai_output = {
        "content_type": "text",
        "main_themes": ["technology", "development"],
        "key_insights": ["Important insight"],
        "actionable_items": ["Task to do"],
    }

    print("1. Validating sample AI output...")
    result = validator.pipeline_validator.schema_validator.validate_ai_output(
        sample_ai_output, "content_analysis"
    )
    print(f"   Valid: {result.is_valid}, Issues: {len(result.issues)}")

    # Example Memory validation

    print("\n2. Validating sample Memory object...")
    # Cannot create memory with mock vectors - real embeddings required
    print("   SKIPPED: Mock vectors not allowed - real embeddings required")

    print("\n✅ Demo completed!")


if __name__ == "__main__":
    run_validation_demo()
