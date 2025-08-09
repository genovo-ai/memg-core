"""
Unified JSON schemas for optimized AI processing - 2-call approach
"""

from typing import Any, Dict

# Unified Content Analysis Schema - combines type detection, summary, and themes
UNIFIED_CONTENT_ANALYSIS_SCHEMA = {
    "type": "object",
    "properties": {
        "content_type": {
            "type": "string",
            "enum": ["document", "note"],
            "description": "Classified content type",
        },
        "summary": {
            "type": "string",
            "description": "Summary of content (only if document type, empty string if note)",
        },
        "key_themes": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Main themes and topics identified in the content",
        },
        "content_complexity": {
            "type": "string",
            "enum": ["SIMPLE", "MODERATE", "COMPLEX", "EXPERT"],
            "description": "Assessed complexity level of the content",
        },
        "domain": {
            "type": "string",
            "description": "Primary domain or field (e.g., technology, business, personal)",
        },
        "priority_entities": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Key entities that should be prioritized for extraction",
        },
        "critical_issues": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "type": {
                        "type": "string",
                        "enum": [
                            "VULNERABILITY",
                            "CONFLICT",
                            "PERFORMANCE",
                            "ERROR",
                            "DEPRECATION",
                        ],
                    },
                    "description": {"type": "string"},
                    "severity": {
                        "type": "string",
                        "enum": ["LOW", "MEDIUM", "HIGH", "CRITICAL"],
                    },
                },
            },
            "description": "Critical issues identified that need immediate attention",
        },
    },
    "required": [
        "content_type",
        "summary",
        "key_themes",
        "content_complexity",
        "domain",
    ],
}


def get_unified_schemas() -> Dict[str, Any]:
    """Get all unified schemas"""
    return {"unified_content_analysis": UNIFIED_CONTENT_ANALYSIS_SCHEMA}
