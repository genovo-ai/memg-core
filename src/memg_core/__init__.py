"""memg-core: True memory for AI - minimal public API"""

# Re-export only the stable public API
from .api.public import MemgClient, add_memory, search
from .core.interfaces.embedder_protocol import EmbedderProtocol

try:
    from .version import __version__
except ModuleNotFoundError:  # pragma: no cover - best effort for local dev
    __version__ = "0.0.0"

__all__ = ["MemgClient", "EmbedderProtocol", "add_memory", "search", "__version__"]
