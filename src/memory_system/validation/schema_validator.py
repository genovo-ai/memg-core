"""
Schema Validator - Validates schemas across the entire memory processing pipeline.
"""

from datetime import datetime
from enum import Enum
import json
import logging
from typing import Any

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class ValidationLevel(str, Enum):
    """Validation severity levels"""

    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


class ValidationIssue(BaseModel):
    """Individual validation issue"""

    level: ValidationLevel
    component: str = Field(..., description="Component being validated")
    field: str | None = Field(None, description="Specific field with issue")
    message: str = Field(..., description="Description of the issue")
    expected: str | None = Field(None, description="Expected value/type")
    actual: str | None = Field(None, description="Actual value/type")
    suggestion: str | None = Field(None, description="How to fix")


class ValidationResult(BaseModel):
    """Result of schema validation"""

    is_valid: bool
    component: str
    issues: list[ValidationIssue] = Field(default_factory=list)
    validated_at: datetime = Field(default_factory=datetime.now)

    @property
    def has_errors(self) -> bool:
        return any(
            issue.level in [ValidationLevel.ERROR, ValidationLevel.CRITICAL]
            for issue in self.issues
        )

    @property
    def has_warnings(self) -> bool:
        return any(issue.level == ValidationLevel.WARNING for issue in self.issues)

    def add_issue(
        self,
        level: ValidationLevel,
        component: str,
        message: str,
        field: str = None,
        expected: str = None,
        actual: str = None,
        suggestion: str = None,
    ):
        """Add a validation issue"""
        issue = ValidationIssue(
            level=level,
            component=component,
            field=field,
            message=message,
            expected=expected,
            actual=actual,
            suggestion=suggestion,
        )
        self.issues.append(issue)

        # Update overall validity
        if level in [ValidationLevel.ERROR, ValidationLevel.CRITICAL]:
            self.is_valid = False


class SchemaValidator:
    """
    Comprehensive schema validator for the memory processing pipeline.

    Validates:
    1. AI output against JSON schemas
    2. Pydantic model conversions
    3. Database schema compatibility
    4. Data type consistency
    """

    def __init__(self):
        """Initialize the schema validator."""
        self.known_schemas = self._load_known_schemas()
        logger.info("SchemaValidator initialized")

    def _load_known_schemas(self) -> dict[str, dict]:
        """Load known JSON schemas for validation."""
        try:
            from ..utils.schemas import SCHEMAS

            return SCHEMAS
        except ImportError:
            logger.warning("Could not load schemas - validation will be limited")
            return {}

    def validate_ai_output(self, output: dict[str, Any], schema_name: str) -> ValidationResult:
        """
        Validate AI-generated output against expected JSON schema.

        Args:
            output: AI output to validate
            schema_name: Name of the schema to validate against

        Returns:
            ValidationResult with issues found
        """
        result = ValidationResult(is_valid=True, component=f"AI Output ({schema_name})")

        if schema_name not in self.known_schemas:
            result.add_issue(
                ValidationLevel.ERROR,
                "Schema",
                f"Unknown schema: {schema_name}",
                suggestion=f"Available schemas: {list(self.known_schemas.keys())}",
            )
            return result

        schema = self.known_schemas[schema_name]

        # Validate required fields
        required_fields = schema.get("required", [])
        for field in required_fields:
            if field not in output:
                result.add_issue(
                    ValidationLevel.ERROR,
                    "Required Field",
                    f"Missing required field: {field}",
                    field=field,
                    expected="present",
                    actual="missing",
                    suggestion=f"Ensure AI generates field '{field}'",
                )

        # Validate field types
        properties = schema.get("properties", {})
        for field, value in output.items():
            if field in properties:
                expected_type = properties[field].get("type")
                actual_type = self._get_type_name(value)

                if not self._types_compatible(expected_type, actual_type, value):
                    result.add_issue(
                        ValidationLevel.ERROR,
                        "Type Mismatch",
                        f"Field '{field}' has wrong type",
                        field=field,
                        expected=expected_type,
                        actual=actual_type,
                        suggestion=f"AI should generate {expected_type} for field '{field}'",
                    )

        # Validate array items if applicable
        for field, value in output.items():
            if field in properties and isinstance(value, list):
                self._validate_array_items(result, field, value, properties[field])

        logger.debug(f"AI output validation: {len(result.issues)} issues found")
        return result

    def validate_model_conversion(
        self, source_data: dict, target_model_class, converted_obj
    ) -> ValidationResult:
        """
        Validate conversion from raw data to Pydantic model.

        Args:
            source_data: Original data
            target_model_class: Target Pydantic model class
            converted_obj: Converted model instance

        Returns:
            ValidationResult with conversion issues
        """
        result = ValidationResult(
            is_valid=True, component=f"Model Conversion ({target_model_class.__name__})"
        )

        try:
            # Validate all fields were converted
            model_fields = target_model_class.model_fields

            for field_name, field_info in model_fields.items():
                if hasattr(converted_obj, field_name):
                    value = getattr(converted_obj, field_name)

                    # Check for None values in required fields
                    if field_info.is_required() and value is None:
                        result.add_issue(
                            ValidationLevel.ERROR,
                            "Required Field",
                            f"Required field '{field_name}' is None after conversion",
                            field=field_name,
                            suggestion="Check source data and conversion logic",
                        )

                    # Validate field types
                    if value is not None:
                        expected_type = field_info.annotation
                        if not self._validate_field_type(value, expected_type):
                            result.add_issue(
                                ValidationLevel.WARNING,
                                "Type Warning",
                                f"Field '{field_name}' type may not match annotation",
                                field=field_name,
                                actual=type(value).__name__,
                                suggestion="Review type annotations and conversion",
                            )

        except Exception as e:
            result.add_issue(
                ValidationLevel.CRITICAL,
                "Conversion Error",
                f"Failed to validate model conversion: {str(e)}",
                suggestion="Check model definition and conversion logic",
            )

        return result

    def validate_database_compatibility(self, model_obj, database_type: str) -> ValidationResult:
        """
        Validate model compatibility with database schema.

        Args:
            model_obj: Pydantic model instance
            database_type: Type of database (qdrant/kuzu)

        Returns:
            ValidationResult with database compatibility issues
        """
        result = ValidationResult(
            is_valid=True, component=f"Database Compatibility ({database_type})"
        )

        if database_type.lower() == "qdrant":
            self._validate_qdrant_compatibility(result, model_obj)
        elif database_type.lower() == "kuzu":
            self._validate_kuzu_compatibility(result, model_obj)
        else:
            result.add_issue(
                ValidationLevel.ERROR,
                "Unknown Database",
                f"Unknown database type: {database_type}",
                suggestion="Use 'qdrant' or 'kuzu'",
            )

        return result

    def validate_relationship_schema(self, relationship_data: dict[str, Any]) -> ValidationResult:
        """
        Validate relationship data for Kuzu compatibility.

        Args:
            relationship_data: Relationship properties

        Returns:
            ValidationResult with relationship schema issues
        """
        result = ValidationResult(is_valid=True, component="Relationship Schema")

        # Check for SQL-safe relationship type
        if "relationship_type" in relationship_data:
            rel_type = relationship_data["relationship_type"]
            if not isinstance(rel_type, str):
                result.add_issue(
                    ValidationLevel.ERROR,
                    "Relationship Type",
                    "relationship_type must be string",
                    field="relationship_type",
                    actual=type(rel_type).__name__,
                    suggestion="Ensure AI generates string relationship types",
                )
            elif " " in rel_type or any(c in rel_type for c in "!@#$%^&*()[]{}+=<>?/|\\-"):
                result.add_issue(
                    ValidationLevel.ERROR,  # Changed to ERROR since this causes SQL failures
                    "Relationship Type",
                    "relationship_type contains spaces or special characters that cause SQL errors",
                    field="relationship_type",
                    actual=rel_type,
                    suggestion="Use UPPERCASE_UNDERSCORE format (e.g., 'WORKS_WITH_CONTAINERS')",
                )

        # Validate property types for Kuzu
        kuzu_type_map = {
            "confidence": (float, int),
            "is_valid": bool,
            "created_at": str,
            "relationship_type": str,
        }

        for prop, value in relationship_data.items():
            if prop in kuzu_type_map:
                expected_types = kuzu_type_map[prop]
                if not isinstance(expected_types, tuple):
                    expected_types = (expected_types,)

                if not isinstance(value, expected_types):
                    result.add_issue(
                        ValidationLevel.ERROR,
                        "Property Type",
                        f"Property '{prop}' has wrong type for Kuzu",
                        field=prop,
                        expected=f"one of {[t.__name__ for t in expected_types]}",
                        actual=type(value).__name__,
                        suggestion=f"Convert {prop} to appropriate type",
                    )

        return result

    def _validate_qdrant_compatibility(self, result: ValidationResult, model_obj):
        """Validate compatibility with Qdrant vector database."""
        # Check for vector field
        if hasattr(model_obj, "vector"):
            vector = model_obj.vector
            if vector is not None:
                if not isinstance(vector, list):
                    result.add_issue(
                        ValidationLevel.ERROR,
                        "Vector Type",
                        "Vector must be a list for Qdrant",
                        field="vector",
                        actual=type(vector).__name__,
                        suggestion="Ensure vector is List[float]",
                    )
                elif len(vector) == 0:
                    result.add_issue(
                        ValidationLevel.ERROR,
                        "Vector Length",
                        "Vector cannot be empty",
                        field="vector",
                        suggestion="Generate proper embedding vector",
                    )
                elif not all(isinstance(x, (int, float)) for x in vector):
                    result.add_issue(
                        ValidationLevel.ERROR,
                        "Vector Elements",
                        "Vector must contain only numbers",
                        field="vector",
                        suggestion="Ensure all vector elements are float/int",
                    )

        # Check payload compatibility
        if hasattr(model_obj, "to_qdrant_payload"):
            try:
                payload = model_obj.to_qdrant_payload()
                # Validate JSON serializable
                json.dumps(payload)
            except Exception as e:
                result.add_issue(
                    ValidationLevel.ERROR,
                    "Payload Serialization",
                    f"Qdrant payload not JSON serializable: {str(e)}",
                    suggestion="Ensure all payload values are JSON serializable",
                )

    def _validate_kuzu_compatibility(self, result: ValidationResult, model_obj):
        """Validate compatibility with Kuzu graph database."""
        # Check node properties
        if hasattr(model_obj, "to_kuzu_node"):
            try:
                node_props = model_obj.to_kuzu_node()
                for prop, value in node_props.items():
                    if not self._is_kuzu_compatible_type(value):
                        result.add_issue(
                            ValidationLevel.WARNING,
                            "Kuzu Type",
                            f"Property '{prop}' may not be Kuzu compatible",
                            field=prop,
                            actual=type(value).__name__,
                            suggestion="Use string, number, or boolean types",
                        )
            except Exception as e:
                result.add_issue(
                    ValidationLevel.ERROR,
                    "Node Conversion",
                    f"Failed to convert to Kuzu node: {str(e)}",
                    suggestion="Check to_kuzu_node() method",
                )

    def _get_type_name(self, value) -> str:
        """Get type name for validation."""
        if isinstance(value, list):
            return "array"
        if isinstance(value, dict):
            return "object"
        if isinstance(value, str):
            return "string"
        if isinstance(value, bool):
            return "boolean"
        if isinstance(value, (int, float)):
            return "number"
        return type(value).__name__

    def _types_compatible(self, expected: str, actual: str, value) -> bool:
        """Check if types are compatible."""
        if expected == actual:
            return True
        if expected == "number" and actual in ["int", "float"]:
            return True
        if expected == "array" and isinstance(value, list):
            return True
        if expected == "object" and isinstance(value, dict):
            return True
        return False

    def _validate_array_items(
        self,
        result: ValidationResult,
        field: str,
        array_value: list,
        field_schema: dict,
    ):
        """Validate array items against schema."""
        items_schema = field_schema.get("items")
        if items_schema and isinstance(items_schema, dict):
            item_type = items_schema.get("type")
            for i, item in enumerate(array_value):
                actual_type = self._get_type_name(item)
                if not self._types_compatible(item_type, actual_type, item):
                    result.add_issue(
                        ValidationLevel.WARNING,
                        "Array Item Type",
                        f"Array '{field}' item {i} has wrong type",
                        field=f"{field}[{i}]",
                        expected=item_type,
                        actual=actual_type,
                    )

    def _validate_field_type(self, value, expected_annotation) -> bool:
        """Validate field type against annotation."""
        # Basic type checking - could be enhanced
        try:
            if hasattr(expected_annotation, "__origin__"):
                # Handle generic types like List[str], Optional[str], etc.
                return True  # Simplified for now
            return isinstance(value, expected_annotation)
        except Exception:
            return True  # If we can't validate, assume it's ok

    def _is_kuzu_compatible_type(self, value) -> bool:
        """Check if value type is compatible with Kuzu."""
        return isinstance(value, (str, int, float, bool, type(None)))
