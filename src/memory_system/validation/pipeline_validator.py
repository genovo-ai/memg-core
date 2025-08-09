"""
Pipeline Validator - Validates the entire memory processing pipeline end-to-end.
"""

import logging
import os
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from ..models import ContentAnalysis, Entity, Memory, MemoryExtraction, Relationship
from .schema_validator import SchemaValidator, ValidationLevel, ValidationResult

logger = logging.getLogger(__name__)


class PipelineValidationReport(BaseModel):
    """Complete validation report for the entire pipeline"""

    pipeline_valid: bool
    total_issues: int
    error_count: int
    warning_count: int
    validation_results: List[ValidationResult] = Field(default_factory=list)

    @property
    def has_critical_issues(self) -> bool:
        return any(result.has_errors for result in self.validation_results)

    def add_validation_result(self, result: ValidationResult):
        """Add a validation result to the report"""
        self.validation_results.append(result)
        self.total_issues += len(result.issues)
        self.error_count += sum(
            1
            for issue in result.issues
            if issue.level in [ValidationLevel.ERROR, ValidationLevel.CRITICAL]
        )
        self.warning_count += sum(
            1 for issue in result.issues if issue.level == ValidationLevel.WARNING
        )

        # Update overall validity
        if result.has_errors:
            self.pipeline_valid = False


class PipelineValidator:
    """
    End-to-end pipeline validator for the memory processing system.

    Validates the complete flow:
    1. AI Output → Schema Validation
    2. Schema → Model Conversion
    3. Model → Database Compatibility
    4. Cross-component Consistency
    """

    def __init__(self):
        """Initialize the pipeline validator."""
        self.schema_validator = SchemaValidator()
        logger.info("PipelineValidator initialized")

    def validate_complete_pipeline(
        self,
        ai_content_analysis: Dict[str, Any],
        ai_memory_extraction: Dict[str, Any],
        ai_entity_extraction: Optional[Dict[str, Any]],
        content_analysis_model: ContentAnalysis,
        memory_extraction_model: MemoryExtraction,
        memory_objects: List[Memory],
        extracted_entities: List[Entity] = None,
        extracted_relationships: List[Relationship] = None,
    ) -> PipelineValidationReport:
        """
        Validate the complete memory processing pipeline.

        Args:
            ai_content_analysis: Raw AI output for content analysis
            ai_memory_extraction: Raw AI output for memory extraction
            ai_entity_extraction: Raw AI output for entity extraction (optional)
            content_analysis_model: Converted ContentAnalysis model
            memory_extraction_model: Converted MemoryExtraction model
            memory_objects: Final Memory objects
            extracted_entities: Extracted Entity objects (optional)
            extracted_relationships: Extracted Relationship objects (optional)

        Returns:
            Complete validation report
        """
        report = PipelineValidationReport(
            pipeline_valid=True, total_issues=0, error_count=0, warning_count=0
        )

        logger.info("Starting complete pipeline validation")

        # Step 1: Validate AI outputs against schemas
        self._validate_ai_outputs(
            report, ai_content_analysis, ai_memory_extraction, ai_entity_extraction
        )

        # Step 2: Validate model conversions
        self._validate_model_conversions(
            report,
            ai_content_analysis,
            ai_memory_extraction,
            content_analysis_model,
            memory_extraction_model,
        )

        # Step 3: Validate memory objects
        self._validate_memory_objects(report, memory_objects)

        # Step 4: Validate entities and relationships if present
        if extracted_entities:
            self._validate_entities(report, extracted_entities)

        if extracted_relationships:
            self._validate_relationships(report, extracted_relationships)

        # Step 5: Cross-component validation
        self._validate_cross_component_consistency(report, memory_extraction_model, memory_objects)

        logger.info(
            f"Pipeline validation complete: {report.error_count} errors, "
            f"{report.warning_count} warnings"
        )
        return report

    def validate_memory_creation_flow(
        self,
        content: str,
        ai_analysis: Dict[str, Any],
        ai_extraction: Dict[str, Any],
        final_memories: List[Memory],
    ) -> PipelineValidationReport:
        """
        Simplified validation for just the memory creation flow.

        Args:
            content: Original content
            ai_analysis: AI content analysis output
            ai_extraction: AI memory extraction output
            final_memories: Final created memories

        Returns:
            Validation report for memory creation
        """
        report = PipelineValidationReport(
            pipeline_valid=True, total_issues=0, error_count=0, warning_count=0
        )

        # Validate AI outputs
        content_result = self.schema_validator.validate_ai_output(ai_analysis, "content_analysis")
        extraction_result = self.schema_validator.validate_ai_output(
            ai_extraction, "memory_extraction"
        )

        report.add_validation_result(content_result)
        report.add_validation_result(extraction_result)

        # Validate final memories
        for i, memory in enumerate(final_memories):
            memory_result = self.schema_validator.validate_database_compatibility(memory, "qdrant")
            memory_result.component = f"Memory {i+1} (Qdrant)"
            report.add_validation_result(memory_result)

            kuzu_result = self.schema_validator.validate_database_compatibility(memory, "kuzu")
            kuzu_result.component = f"Memory {i+1} (Kuzu)"
            report.add_validation_result(kuzu_result)

        return report

    def _validate_ai_outputs(
        self,
        report: PipelineValidationReport,
        ai_content_analysis: Dict[str, Any],
        ai_memory_extraction: Dict[str, Any],
        ai_entity_extraction: Optional[Dict[str, Any]],
    ):
        """Validate all AI outputs against schemas."""

        # Validate content analysis
        content_result = self.schema_validator.validate_ai_output(
            ai_content_analysis, "content_analysis"
        )
        report.add_validation_result(content_result)

        # Validate memory extraction
        extraction_result = self.schema_validator.validate_ai_output(
            ai_memory_extraction, "memory_extraction"
        )
        report.add_validation_result(extraction_result)

        # Validate entity extraction if present
        if ai_entity_extraction:
            entity_result = self.schema_validator.validate_ai_output(
                ai_entity_extraction, "entity_relationship_extraction"
            )
            report.add_validation_result(entity_result)

    def _validate_model_conversions(
        self,
        report: PipelineValidationReport,
        ai_content_analysis: Dict[str, Any],
        ai_memory_extraction: Dict[str, Any],
        content_analysis_model: ContentAnalysis,
        memory_extraction_model: MemoryExtraction,
    ):
        """Validate conversions from AI output to Pydantic models."""

        # Validate content analysis conversion
        content_conversion = self.schema_validator.validate_model_conversion(
            ai_content_analysis, ContentAnalysis, content_analysis_model
        )
        report.add_validation_result(content_conversion)

        # Validate memory extraction conversion
        extraction_conversion = self.schema_validator.validate_model_conversion(
            ai_memory_extraction, MemoryExtraction, memory_extraction_model
        )
        report.add_validation_result(extraction_conversion)

    def _validate_memory_objects(
        self, report: PipelineValidationReport, memory_objects: List[Memory]
    ):
        """Validate Memory objects for database compatibility."""
        for i, memory in enumerate(memory_objects):
            # Validate Qdrant compatibility
            qdrant_result = self.schema_validator.validate_database_compatibility(memory, "qdrant")
            qdrant_result.component = f"Memory {i+1} Qdrant Compatibility"
            report.add_validation_result(qdrant_result)

            # Validate Kuzu compatibility
            kuzu_result = self.schema_validator.validate_database_compatibility(memory, "kuzu")
            kuzu_result.component = f"Memory {i+1} Kuzu Compatibility"
            report.add_validation_result(kuzu_result)

            # Additional memory-specific validations
            memory_validation = ValidationResult(is_valid=True, component=f"Memory {i+1} Content")

            # Check for empty content
            if not memory.content or not memory.content.strip():
                memory_validation.add_issue(
                    ValidationLevel.ERROR,
                    "Empty Content",
                    "Memory content is empty or only whitespace",
                    field="content",
                    suggestion="Ensure memory extraction generates meaningful content",
                )

            # Check for reasonable content length
            if len(memory.content) < 10:
                memory_validation.add_issue(
                    ValidationLevel.WARNING,
                    "Short Content",
                    f"Memory content is very short ({len(memory.content)} chars)",
                    field="content",
                    suggestion="Consider if this memory provides sufficient value",
                )

            # Check vector presence and validity
            if memory.vector is None:
                memory_validation.add_issue(
                    ValidationLevel.ERROR,
                    "Missing Vector",
                    "Memory has no embedding vector",
                    field="vector",
                    suggestion="Generate embedding vector for semantic search",
                )
            else:
                # Get expected dimension from environment
                expected_dim = int(os.getenv("EMBEDDING_DIMENSION_LEN", "768"))
                if len(memory.vector) != expected_dim:  # Embedding dimension from env
                    memory_validation.add_issue(
                        ValidationLevel.WARNING,
                        "Unexpected Vector Dimension",
                        f"Vector has {len(memory.vector)} dimensions, expected {expected_dim}",
                        field="vector",
                        suggestion="Verify embedding model and generation process",
                    )

            report.add_validation_result(memory_validation)

    def _validate_entities(self, report: PipelineValidationReport, entities: List[Entity]):
        """Validate Entity objects."""
        for i, entity in enumerate(entities):
            entity_result = self.schema_validator.validate_database_compatibility(entity, "kuzu")
            entity_result.component = f"Entity {i+1} ({entity.name})"
            report.add_validation_result(entity_result)

    def _validate_relationships(
        self, report: PipelineValidationReport, relationships: List[Relationship]
    ):
        """Validate Relationship objects."""
        for i, relationship in enumerate(relationships):
            # Convert to dict for relationship schema validation
            rel_data = relationship.to_kuzu_props()
            rel_result = self.schema_validator.validate_relationship_schema(rel_data)
            rel_result.component = f"Relationship {i+1} ({relationship.relationship_type})"
            report.add_validation_result(rel_result)

    def _validate_cross_component_consistency(
        self,
        report: PipelineValidationReport,
        memory_extraction: MemoryExtraction,
        memory_objects: List[Memory],
    ):
        """Validate consistency across components."""
        consistency_result = ValidationResult(
            is_valid=True, component="Cross-Component Consistency"
        )

        # Check if extraction and final memories match in count
        extracted_count = len(memory_extraction.memories)
        final_count = len(memory_objects)

        if extracted_count != final_count:
            consistency_result.add_issue(
                ValidationLevel.WARNING,
                "Memory Count Mismatch",
                f"Extracted {extracted_count} memories but created {final_count} objects",
                suggestion="Review memory object creation logic",
            )

        # Check if extracted content appears in final memories
        extracted_contents = set(memory_extraction.memories)
        final_contents = set(memory.content for memory in memory_objects)

        missing_content = extracted_contents - final_contents
        if missing_content:
            consistency_result.add_issue(
                ValidationLevel.ERROR,
                "Missing Content",
                f"{len(missing_content)} extracted memories not found in final objects",
                suggestion="Ensure all extracted memories are converted to objects",
            )

        report.add_validation_result(consistency_result)

    def print_validation_report(self, report: PipelineValidationReport):
        """Print a formatted validation report."""
        print(f"\n{'='*60}")
        print("🔍 PIPELINE VALIDATION REPORT")
        print(f"{'='*60}")
        print(f"Overall Status: {'✅ PASS' if report.pipeline_valid else '❌ FAIL'}")
        print(f"Total Issues: {report.total_issues}")
        print(f"Errors: {report.error_count}")
        print(f"Warnings: {report.warning_count}")
        print()

        for result in report.validation_results:
            if result.issues:
                print(f"📋 {result.component}:")
                for issue in result.issues:
                    icon = (
                        "❌"
                        if issue.level in [ValidationLevel.ERROR, ValidationLevel.CRITICAL]
                        else "⚠️"
                    )
                    print(f"  {icon} {issue.message}")
                    if issue.field:
                        print(f"     Field: {issue.field}")
                    if issue.expected and issue.actual:
                        print(f"     Expected: {issue.expected}, Got: {issue.actual}")
                    if issue.suggestion:
                        print(f"     💡 {issue.suggestion}")
                print()

        if report.pipeline_valid:
            print("🎯 Pipeline validation PASSED! All components are schema-compliant.")
        else:
            print("⚠️ Pipeline validation FAILED! Please address the errors above.")
        print(f"{'='*60}\n")
