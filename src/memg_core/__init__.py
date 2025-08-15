"""memg-core: True memory for AI - minimal public API"""

# Re-export only the stable public API
from .api.public import add_memory, search
from .version import __version__

__all__ = ["add_memory", "search", "__version__"]
