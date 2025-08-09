#!/usr/bin/env python3
"""
Sync Memory Wrapper - Simplified g^mem interface
Provides simple sync methods for document and note storage
"""

import asyncio
import threading
from typing import Any, Dict, List, Optional

from .config import MemGConfig, get_config
from .exceptions import ProcessingError, ValidationError
from .kuzu_graph.interface import KuzuInterface
from .models.api import CreateMemoryRequest, ProcessingResponse
from .models.core import MemoryType
from .processing.memory_retriever import MemoryRetriever
from .processing.unified_memory_processor import UnifiedMemoryProcessor
from .qdrant.interface import QdrantInterface


class SyncMemorySystem:
    """
    Simplified sync wrapper for g^mem system
    Handles document and note storage with AI-driven type detection
    """

    def __init__(self, config: Optional[MemGConfig] = None):
        """Initialize simplified memory system"""
        try:
            # Use provided config or load from environment/defaults
            self.config = config or get_config().memg

            # Initialize interfaces
            self.qdrant_interface = QdrantInterface()
            self.kuzu_interface = KuzuInterface()

            # Initialize unified processor (2-call approach)
            self.processor = UnifiedMemoryProcessor(
                qdrant=self.qdrant_interface,
                kuzu=self.kuzu_interface,
            )
            self.retriever = MemoryRetriever(
                qdrant_interface=self.qdrant_interface,
                kuzu_interface=self.kuzu_interface,
            )

            # Event loop for async operations
            self._loop = None
            self._thread = None
            self._start_background_loop()

            from .logging_config import get_logger

            logger = get_logger("sync_wrapper")
            logger.info(
                "g^mem System initialized successfully",
                extra={"score_threshold": self.config.score_threshold},
            )

        except (FileNotFoundError, PermissionError) as e:
            from .exceptions import StorageError
            from .logging_config import log_error

            log_error("sync_wrapper", "initialization", e)
            raise StorageError(
                "Storage initialization failed",
                operation="initialization",
                original_error=e,
            )
        except (ConnectionError, TimeoutError) as e:
            from .exceptions import NetworkError
            from .logging_config import log_error

            log_error("sync_wrapper", "initialization", e)
            raise NetworkError(
                "Network initialization failed",
                operation="initialization",
                original_error=e,
            )
        except Exception as e:
            from .exceptions import wrap_exception
            from .logging_config import log_error

            log_error("sync_wrapper", "initialization", e)
            raise wrap_exception(e, "sync_wrapper_initialization")

    def _start_background_loop(self):
        """Start background event loop for async operations"""

        def run_loop():
            self._loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self._loop)
            self._loop.run_forever()

        self._thread = threading.Thread(target=run_loop, daemon=True)
        self._thread.start()

        # Wait for loop to be ready
        while self._loop is None:
            threading.Event().wait(0.01)

    def _run_async(self, coro):
        """Run async coroutine in background loop"""
        if self._loop is None:
            raise RuntimeError("Background loop not initialized")

        future = asyncio.run_coroutine_threadsafe(coro, self._loop)
        return future.result()

    def add(
        self,
        content: str,
        user_id: str,
        memory_type: Optional[MemoryType] = None,
        title: Optional[str] = None,
        source: str = "user",
        tags: Optional[List[str]] = None,
        project_id: Optional[str] = None,
        project_name: Optional[str] = None,
    ) -> ProcessingResponse:
        """
        Add a memory to the system with automatic type detection.

        Args:
            content: Memory content to store
            user_id: User ID for memory isolation
            memory_type: Optional type hint (will be AI-verified)
            title: Optional title
            source: Source of the memory
            tags: Optional tags list
            project_id: Optional project ID for scoping
            project_name: Optional project name for display

        Returns:
            ProcessingResponse with detailed results
        """
        try:
            request = CreateMemoryRequest(
                content=content,
                user_id=user_id,
                memory_type=memory_type,
                title=title,
                source=source,
                tags=tags or [],
                project_id=project_id,
                project_name=project_name,
            )

            # Run async operation in background loop
            result = self._run_async(self.processor.process_memory(request))
            return result

        except (ValidationError, ProcessingError) as e:
            from .logging_config import log_error

            log_error("sync_wrapper", "add_memory", e, content_length=len(content))
            return ProcessingResponse(
                success=False,
                memory_id="",
                final_type=memory_type or MemoryType.NOTE,
                ai_verified=False,
                summary_generated=False,
                processing_time_ms=0.0,
                word_count=len(content.split()),
                error=str(e),
            )
        except Exception as e:
            from .exceptions import wrap_exception
            from .logging_config import log_error

            wrapped_error = wrap_exception(e, "add_memory", {"content_length": len(content)})
            log_error("sync_wrapper", "add_memory", wrapped_error, content_length=len(content))
            return ProcessingResponse(
                success=False,
                memory_id="",
                final_type=memory_type or MemoryType.NOTE,
                ai_verified=False,
                summary_generated=False,
                processing_time_ms=0.0,
                word_count=len(content.split()),
                error=str(wrapped_error),
            )

    def add_document(
        self,
        content: str,
        title: Optional[str] = None,
        source: str = "user",
        tags: Optional[List[str]] = None,
    ) -> ProcessingResponse:
        """
        Add a document to the system (will generate summary).

        Args:
            content: Document content to store
            title: Optional title
            source: Source of the document
            tags: Optional tags list

        Returns:
            ProcessingResponse with detailed results
        """
        return self.add(
            content=content,
            memory_type=MemoryType.DOCUMENT,
            title=title,
            source=source,
            tags=tags,
        )

    def add_note(
        self,
        content: str,
        title: Optional[str] = None,
        source: str = "user",
        tags: Optional[List[str]] = None,
    ) -> ProcessingResponse:
        """
        Add a note to the system (brief insight, no summary).

        Args:
            content: Note content to store
            title: Optional title
            source: Source of the note
            tags: Optional tags list

        Returns:
            ProcessingResponse with detailed results
        """
        return self.add(
            content=content,
            memory_type=MemoryType.NOTE,
            title=title,
            source=source,
            tags=tags,
        )

    def search(
        self,
        query: str,
        user_id: Optional[str] = None,
        limit: int = 5,
        memory_types: Optional[List[MemoryType]] = None,
    ) -> List[Dict[str, Any]]:
        """
        Search memories using semantic similarity.

        Args:
            query: Search query
            user_id: User ID for memory isolation (optional for backward compatibility)
            limit: Maximum results to return
            memory_types: Types to search (default: all types)

        Returns:
            List of memory results
        """
        try:
            # Use configured score threshold
            score_threshold = self.config.score_threshold

            # Run async operation in background loop
            results = self._run_async(
                self.retriever.search_memories(
                    query=query,
                    user_id=user_id,
                    limit=limit,
                    score_threshold=score_threshold,
                )
            )

            # Filter by memory types if specified
            if memory_types:
                type_values = [t.value for t in memory_types]
                results = [r for r in results if r.memory.memory_type.value in type_values]

            # Format results for output
            formatted_results = [
                {
                    "content": r.memory.content,
                    "type": r.memory.memory_type.value,
                    "summary": r.memory.summary,
                    "score": r.score,
                    "source": r.memory.source or "unknown",
                    "memory_id": r.memory.id,
                    "title": r.memory.title,
                    "tags": r.memory.tags,
                    "word_count": r.memory.word_count(),
                    "created_at": r.memory.created_at.isoformat(),
                }
                for r in results
            ]

            return formatted_results

        except (ValidationError, ProcessingError) as e:
            from .logging_config import log_error

            log_error("sync_wrapper", "search_memories", e, query=query, limit=limit)
            return []
        except Exception as e:
            from .exceptions import wrap_exception
            from .logging_config import log_error

            wrapped_error = wrap_exception(e, "search_memories", {"query": query, "limit": limit})
            log_error(
                "sync_wrapper",
                "search_memories",
                wrapped_error,
                query=query,
                limit=limit,
            )
            return []

    def search_documents(self, query: str, limit: int = 5) -> List[Dict[str, Any]]:
        """Search only documents"""
        return self.search(query, limit, [MemoryType.DOCUMENT])

    def search_notes(self, query: str, limit: int = 5) -> List[Dict[str, Any]]:
        """Search only notes"""
        return self.search(query, limit, [MemoryType.NOTE])

    def get_stats(self) -> Dict[str, Any]:
        """Get system statistics"""
        base_stats = {
            "processor_initialized": self.processor is not None,
            "retriever_initialized": self.retriever is not None,
            "qdrant_available": self.qdrant_interface is not None,
            "kuzu_available": self.kuzu_interface is not None,
            "system_type": "g^mem_simplified",
        }

        # Add configuration info
        config_stats = {
            "memg_config": self.config.to_dict(),
        }

        base_stats.update(config_stats)
        return base_stats

    def update_config(self, **kwargs) -> bool:
        """
        Update g^mem configuration parameters at runtime.

        Args:
            **kwargs: Configuration parameters to update

        Returns:
            bool: True if successful
        """
        try:
            # Create new configuration with updates
            self.config = self.config.update(**kwargs)

            from .logging_config import get_logger

            logger = get_logger("sync_wrapper")
            logger.info("Configuration updated", extra={"updates": kwargs})
            return True

        except (ValidationError, ValueError) as e:
            from .logging_config import log_error

            log_error("sync_wrapper", "update_config", e, updates=kwargs)
            return False
        except Exception as e:
            from .exceptions import wrap_exception
            from .logging_config import log_error

            wrapped_error = wrap_exception(e, "update_config", {"updates": kwargs})
            log_error("sync_wrapper", "update_config", wrapped_error, updates=kwargs)
            return False

    # Legacy support methods (simplified)
    def add_from_message_pair(
        self,
        current_message: str,
        previous_message: Optional[str] = None,
        speaker: Optional[str] = None,
        conversation_id: Optional[str] = None,
        **kwargs,
    ) -> bool:
        """
        Legacy support: Convert conversation to note.

        Args:
            current_message: Current message content
            previous_message: Previous message content (optional)
            speaker: Message speaker
            conversation_id: Conversation identifier

        Returns:
            bool: True if successful
        """
        try:
            # Combine messages into single content
            content_parts = []
            if previous_message:
                content_parts.append(f"Previous: {previous_message}")
            content_parts.append(f"Current: {current_message}")

            content = "\n".join(content_parts)

            # Add as note with conversation context
            result = self.add_note(
                content=content,
                source="conversation",
                tags=([f"conversation:{conversation_id}"] if conversation_id else ["conversation"]),
            )

            return result.success

        except (ValidationError, ProcessingError) as e:
            from .logging_config import log_error

            log_error(
                "sync_wrapper",
                "add_from_message_pair",
                e,
                previous_length=len(previous_message) if previous_message else 0,
                current_length=len(current_message),
            )
            return False
        except Exception as e:
            from .exceptions import wrap_exception
            from .logging_config import log_error

            wrapped_error = wrap_exception(
                e,
                "add_from_message_pair",
                {
                    "previous_length": len(previous_message) if previous_message else 0,
                    "current_length": len(current_message),
                },
            )
            log_error("sync_wrapper", "add_from_message_pair", wrapped_error)
            return False

    def __del__(self):
        """Cleanup background loop"""
        if hasattr(self, "_loop") and self._loop and self._loop.is_running():
            self._loop.call_soon_threadsafe(self._loop.stop)
