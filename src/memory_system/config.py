"""
Memory System Configuration - g^mem Essential Settings

Simplified configuration focusing on core document/note processing
with minimal, essential parameters for the g^mem system.
"""

import os
from dataclasses import dataclass, field
from typing import Any, Dict


@dataclass
class MemGConfig:
    """
    Simplified g^mem Configuration for document and note processing.

    Focuses on essential parameters for AI-driven type detection,
    document summarization, and semantic search.
    """

    # Core similarity and scoring thresholds
    similarity_threshold: float = 0.7  # For conflict detection (future use)
    score_threshold: float = 0.3  # Minimum score for search results
    high_similarity_threshold: float = 0.9  # For duplicate detection (future use)

    # Processing settings
    max_summary_tokens: int = 750  # Max tokens for document summarization (latency control)
    enable_ai_type_verification: bool = True  # AI-based type detection
    enable_temporal_reasoning: bool = False  # Enable temporal reasoning for memory updates

    # Performance settings
    vector_dimension: int = 768  # Embedding dimension
    batch_processing_size: int = 50  # Batch size for bulk operations

    # Template settings
    template_name: str = "default"  # Active template name

    # Database settings
    qdrant_collection_name: str = "memories"
    kuzu_database_path: str = "kuzu_db"

    def __post_init__(self):
        """Validate configuration parameters"""
        if not 0.0 <= self.similarity_threshold <= 1.0:
            raise ValueError("similarity_threshold must be between 0.0 and 1.0")
        if not 0.0 <= self.score_threshold <= 1.0:
            raise ValueError("score_threshold must be between 0.0 and 1.0")
        if not 0.0 <= self.high_similarity_threshold <= 1.0:
            raise ValueError("high_similarity_threshold must be between 0.0 and 1.0")
        if self.max_summary_tokens < 100:
            raise ValueError("max_summary_tokens must be at least 100")

    def to_dict(self) -> Dict[str, Any]:
        """Convert configuration to dictionary"""
        return {
            "similarity_threshold": self.similarity_threshold,
            "score_threshold": self.score_threshold,
            "high_similarity_threshold": self.high_similarity_threshold,
            "max_summary_tokens": self.max_summary_tokens,
            "enable_ai_type_verification": self.enable_ai_type_verification,
            "vector_dimension": self.vector_dimension,
            "batch_processing_size": self.batch_processing_size,
            "template_name": self.template_name,
            "qdrant_collection_name": self.qdrant_collection_name,
            "kuzu_database_path": self.kuzu_database_path,
        }

    @classmethod
    def from_dict(cls, config_dict: Dict[str, Any]) -> "MemGConfig":
        """Create configuration from dictionary"""
        return cls(**config_dict)

    @classmethod
    def from_env(cls) -> "MemGConfig":
        """Create configuration from environment variables"""
        return cls(
            similarity_threshold=float(os.getenv("MEMG_SIMILARITY_THRESHOLD", "0.7")),
            score_threshold=float(os.getenv("MEMG_SCORE_THRESHOLD", "0.3")),
            high_similarity_threshold=float(os.getenv("MEMG_HIGH_SIMILARITY_THRESHOLD", "0.9")),
            max_summary_tokens=int(os.getenv("MEMG_MAX_SUMMARY_TOKENS", "750")),
            enable_ai_type_verification=os.getenv(
                "MEMG_ENABLE_AI_TYPE_VERIFICATION", "true"
            ).lower()
            == "true",
            vector_dimension=int(os.getenv("MEMG_VECTOR_DIMENSION", "768")),
            batch_processing_size=int(os.getenv("MEMG_BATCH_SIZE", "50")),
            template_name=os.getenv("MEMG_TEMPLATE", "default"),
            qdrant_collection_name=os.getenv("MEMG_QDRANT_COLLECTION", "memories"),
            kuzu_database_path=os.getenv("MEMG_KUZU_DB_PATH", "kuzu_db"),
        )

    def update(self, **kwargs) -> "MemGConfig":
        """Create new configuration with updated values"""
        config_dict = self.to_dict()
        config_dict.update(kwargs)
        return self.from_dict(config_dict)


@dataclass
class MemorySystemConfig:
    """
    System-wide configuration for g^mem.
    Includes core g^mem config plus basic system settings.
    """

    memg: MemGConfig = field(default_factory=MemGConfig)

    # System settings (minimal)
    debug_mode: bool = False
    log_level: str = "INFO"

    # MCP server settings
    mcp_port: int = 8787
    mcp_host: str = "0.0.0.0"  # nosec B104: Server binding for containerized deployment

    def __post_init__(self):
        """Validate system configuration"""
        if self.mcp_port < 1024 or self.mcp_port > 65535:
            raise ValueError("mcp_port must be between 1024 and 65535")
        if self.log_level not in ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]:
            raise ValueError("log_level must be a valid logging level")

    @classmethod
    def from_env(cls) -> "MemorySystemConfig":
        """Create system configuration from environment variables"""
        return cls(
            memg=MemGConfig.from_env(),
            debug_mode=os.getenv("MEMORY_SYSTEM_DEBUG", "false").lower() == "true",
            log_level=os.getenv("MEMORY_SYSTEM_LOG_LEVEL", "INFO").upper(),
            mcp_port=int(os.getenv("MEMORY_SYSTEM_MCP_PORT", "8787")),
            mcp_host=os.getenv("MEMORY_SYSTEM_MCP_HOST", "0.0.0.0"),  # nosec B104
        )


# Default configurations
DEFAULT_MEMG_CONFIG = MemGConfig()
DEFAULT_SYSTEM_CONFIG = MemorySystemConfig()


def get_config() -> MemorySystemConfig:
    """Get system configuration, preferring environment variables"""
    try:
        return MemorySystemConfig.from_env()
    except Exception as e:
        print(f"Warning: Failed to load config from environment: {e}")
        return DEFAULT_SYSTEM_CONFIG
