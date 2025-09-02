"""Memory System Configuration - minimal and essential settings"""

from dataclasses import dataclass, field
import os
from typing import Any


@dataclass
class MemGConfig:
    """Core memory system configuration.

    Attributes:
        similarity_threshold: Threshold for conflict detection (0.0-1.0).
        score_threshold: Minimum score for search results (0.0-1.0).
        high_similarity_threshold: Threshold for duplicate detection (0.0-1.0).
        decay_rate: Graph traversal decay rate per hop (0.0-1.0).
        decay_threshold: Minimum neighbor relevance threshold (0.0-1.0).
        enable_ai_type_verification: Enable AI-based type detection.
        enable_temporal_reasoning: Enable temporal reasoning.
        vector_dimension: Embedding dimension size.
        batch_processing_size: Batch size for bulk operations.
        embedder_model: FastEmbed model name.
        template_name: Active template name.
        qdrant_collection_name: Qdrant collection name.
        kuzu_database_path: Kuzu database path.
    """

    # Core similarity and scoring thresholds
    similarity_threshold: float = 0.7  # For conflict detection
    score_threshold: float = 0.3  # Minimum score for search results
    high_similarity_threshold: float = 0.9  # For duplicate detection
    decay_rate: float = 0.9  # Graph traversal decay rate per hop
    decay_threshold: float = 0.1  # Minimum neighbor relevance threshold

    # Processing settings
    enable_ai_type_verification: bool = True  # AI-based type detection
    enable_temporal_reasoning: bool = False  # Enable temporal reasoning

    # Performance settings
    vector_dimension: int = 384  # Embedding dimension
    batch_processing_size: int = 50  # Batch size for bulk operations
    embedder_model: str = "Snowflake/snowflake-arctic-embed-xs"  # FastEmbed model

    # Template settings
    template_name: str = "default"  # Active template name

    # Database settings
    qdrant_collection_name: str = "memories"
    kuzu_database_path: str = "kuzu_db"

    def __post_init__(self):
        """Validate configuration parameters.

        Raises:
            ValueError: If any threshold values are outside valid range [0.0, 1.0].
        """
        if not 0.0 <= self.similarity_threshold <= 1.0:
            raise ValueError("similarity_threshold must be between 0.0 and 1.0")
        if not 0.0 <= self.score_threshold <= 1.0:
            raise ValueError("score_threshold must be between 0.0 and 1.0")
        if not 0.0 <= self.high_similarity_threshold <= 1.0:
            raise ValueError("high_similarity_threshold must be between 0.0 and 1.0")
        if not 0.0 <= self.decay_rate <= 1.0:
            raise ValueError("decay_rate must be between 0.0 and 1.0")
        if not 0.0 <= self.decay_threshold <= 1.0:
            raise ValueError("decay_threshold must be between 0.0 and 1.0")

    def to_dict(self) -> dict[str, Any]:
        """Convert configuration to dictionary.

        Returns:
            dict[str, Any]: Dictionary representation of configuration.
        """
        return {
            "similarity_threshold": self.similarity_threshold,
            "score_threshold": self.score_threshold,
            "high_similarity_threshold": self.high_similarity_threshold,
            "decay_rate": self.decay_rate,
            "decay_threshold": self.decay_threshold,
            "enable_ai_type_verification": self.enable_ai_type_verification,
            "vector_dimension": self.vector_dimension,
            "batch_processing_size": self.batch_processing_size,
            "embedder_model": self.embedder_model,
            "template_name": self.template_name,
            "qdrant_collection_name": self.qdrant_collection_name,
            "kuzu_database_path": self.kuzu_database_path,
        }

    @classmethod
    def from_dict(cls, config_dict: dict[str, Any]) -> "MemGConfig":
        """Create configuration from dictionary.

        Args:
            config_dict: Dictionary containing configuration values.

        Returns:
            MemGConfig: Configuration instance.
        """
        return cls(**config_dict)

    @classmethod
    def from_env(cls) -> "MemGConfig":
        """Create configuration from environment variables.

        Each instance should use explicit environment variables for isolation.
        The core memory system doesn't know or care about server ports.

        Returns:
            MemGConfig: Configuration instance with environment-derived values.
        """
        return cls(
            similarity_threshold=float(os.getenv("MEMG_SIMILARITY_THRESHOLD", "0.7")),
            score_threshold=float(os.getenv("MEMG_SCORE_THRESHOLD", "0.3")),
            high_similarity_threshold=float(os.getenv("MEMG_HIGH_SIMILARITY_THRESHOLD", "0.9")),
            decay_rate=float(os.getenv("MEMG_DECAY_RATE", "0.9")),
            decay_threshold=float(os.getenv("MEMG_DECAY_THRESHOLD", "0.1")),
            enable_ai_type_verification=os.getenv(
                "MEMG_ENABLE_AI_TYPE_VERIFICATION", "true"
            ).lower()
            == "true",
            vector_dimension=int(os.getenv("EMBEDDING_DIMENSION_LEN", "384")),
            batch_processing_size=int(os.getenv("MEMG_BATCH_SIZE", "50")),
            embedder_model=os.getenv("EMBEDDER_MODEL", "Snowflake/snowflake-arctic-embed-xs"),
            template_name=os.getenv("MEMG_TEMPLATE", "default"),
            qdrant_collection_name=os.getenv("MEMG_QDRANT_COLLECTION", "memories"),
            kuzu_database_path=os.getenv("MEMG_KUZU_DB_PATH", "kuzu_db"),
        )


@dataclass
class MemorySystemConfig:
    """Core memory system configuration - NO SERVER CONCERNS.

    Attributes:
        memg: Core memory configuration instance.
        debug_mode: Enable debug mode.
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL).
    """

    memg: MemGConfig = field(default_factory=MemGConfig)

    # Core system settings only
    debug_mode: bool = False
    log_level: str = "INFO"

    def __post_init__(self):
        """Validate core system configuration.

        Raises:
            ValueError: If log_level is not a valid logging level.
        """
        if self.log_level not in ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]:
            raise ValueError("log_level must be a valid logging level")

    @classmethod
    def from_env(cls) -> "MemorySystemConfig":
        """Create core memory system configuration from environment variables.

        Returns:
            MemorySystemConfig: Configuration instance with environment-derived values.
        """
        return cls(
            memg=MemGConfig.from_env(),
            debug_mode=os.getenv("MEMORY_SYSTEM_DEBUG", "false").lower() == "true",
            log_level=os.getenv("MEMORY_SYSTEM_LOG_LEVEL", "INFO").upper(),
        )


# Default configurations
DEFAULT_MEMG_CONFIG = MemGConfig()
DEFAULT_SYSTEM_CONFIG = MemorySystemConfig()


def get_config() -> MemorySystemConfig:
    """Get system configuration, preferring environment variables.

    Returns:
        MemorySystemConfig: System configuration instance.
    """
    return MemorySystemConfig.from_env()
