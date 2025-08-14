"""
Deprecated shim. Kept for backward compatibility in tests.
Do not use; superseded by core/pipeline/indexer.py
"""

import warnings

warnings.warn(
    "memg_core.core.indexing is deprecated. Use memg_core.core.pipeline.indexer instead.",
    DeprecationWarning,
    stacklevel=2,
)
