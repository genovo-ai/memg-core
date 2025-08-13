"""memg-core: True memory for AI - minimal public API"""

# Re-export only the stable public API
from .api.public import add_document, add_note, add_task, search
from .version import __version__

__all__ = ["add_note", "add_document", "add_task", "search", "__version__"]
