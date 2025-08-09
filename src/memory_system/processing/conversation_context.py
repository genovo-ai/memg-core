"""
Conversation Context Manager - Handles conversation summaries and message history.

This module manages the conversation context required for MEM0-style memory processing:
- Conversation summaries (S) with periodic refresh
- Recent message windows (last m messages)
- Message pair creation for memory extraction
"""

import json
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from ..models.core import ConversationSummary, Message, MessagePair
from ..utils.genai import GenAI
from ..utils.prompts import prompt_loader

logger = logging.getLogger(__name__)


class ConversationContextManager:
    """
    Manages conversation context for MEM0-style memory processing.

    Handles:
    - Conversation summary generation and storage
    - Recent message window management
    - Message pair creation for extraction
    """

    def __init__(self, message_window_size: int = 10):
        """
        Initialize conversation context manager.

        Args:
            message_window_size: Number of recent messages to maintain (m parameter)
        """
        self.message_window_size = message_window_size
        self.genai = GenAI(system_instruction="You are a conversation summarization assistant.")

        # In-memory storage for now (TODO: persist to database)
        self._conversation_summaries: Dict[str, ConversationSummary] = {}
        self._conversation_messages: Dict[str, List[Message]] = {}

        logger.info(
            f"ConversationContextManager initialized with window size: {message_window_size}"
        )

    def add_message(
        self,
        conversation_id: str,
        content: str,
        speaker: Optional[str] = None,
        message_type: str = "user",
    ) -> Message:
        """
        Add a message to conversation history.

        Args:
            conversation_id: Unique conversation identifier
            content: Message content
            speaker: Optional speaker identifier
            message_type: Type of message (user, assistant, system)

        Returns:
            Created Message object
        """
        message = Message(
            content=content,
            timestamp=datetime.now(timezone.utc),
            speaker=speaker,
            message_type=message_type,
        )

        # Initialize conversation if needed
        if conversation_id not in self._conversation_messages:
            self._conversation_messages[conversation_id] = []

        # Add message and maintain window
        messages = self._conversation_messages[conversation_id]
        messages.append(message)

        # Keep only recent messages (sliding window)
        if len(messages) > self.message_window_size * 2:  # Keep some buffer
            self._conversation_messages[conversation_id] = messages[-self.message_window_size * 2 :]

        logger.debug(f"Added message to conversation {conversation_id}: {content[:50]}...")
        return message

    def get_message_pair(
        self,
        conversation_id: str,
        current_message: str,
        current_speaker: Optional[str] = None,
        previous_message_content: Optional[str] = None,
        previous_speaker: Optional[str] = None,
    ) -> MessagePair:
        """
        Create a message pair for memory extraction.

        Args:
            conversation_id: Conversation identifier
            current_message: Current message content
            current_speaker: Current message speaker
            previous_message_content: Optional explicit previous message
            previous_speaker: Previous message speaker

        Returns:
            MessagePair ready for memory extraction
        """
        # Add current message to history
        current_msg = self.add_message(conversation_id, current_message, current_speaker)

        # Get or create previous message
        messages = self._conversation_messages.get(conversation_id, [])
        previous_msg = None

        if previous_message_content:
            # Use explicitly provided previous message
            previous_msg = Message(
                content=previous_message_content,
                timestamp=datetime.now(timezone.utc),
                speaker=previous_speaker,
                message_type="user",
            )
        elif len(messages) >= 2:
            # Use previous message from history (excluding current)
            previous_msg = messages[-2]

        # Get conversation summary
        summary = self.get_conversation_summary(conversation_id)
        summary_text = summary.summary if summary else None

        # Get recent messages (excluding current)
        recent_messages = messages[:-1][-self.message_window_size :] if len(messages) > 1 else []

        message_pair = MessagePair(
            previous_message=previous_msg,
            current_message=current_msg,
            conversation_summary=summary_text,
            recent_messages=recent_messages,
        )

        logger.debug(f"Created message pair for conversation {conversation_id}")
        return message_pair

    def get_conversation_summary(self, conversation_id: str) -> Optional[ConversationSummary]:
        """
        Get conversation summary for a conversation.

        Args:
            conversation_id: Conversation identifier

        Returns:
            ConversationSummary if available
        """
        return self._conversation_summaries.get(conversation_id)

    async def generate_conversation_summary(self, conversation_id: str) -> ConversationSummary:
        """
        Generate or refresh conversation summary using GenAI.

        Args:
            conversation_id: Conversation identifier

        Returns:
            Updated ConversationSummary
        """
        messages = self._conversation_messages.get(conversation_id, [])

        if not messages:
            # Empty conversation
            summary = ConversationSummary(
                summary="Empty conversation - no messages yet.",
                last_updated=datetime.now(timezone.utc),
                message_count=0,
                participants=[],
            )
            self._conversation_summaries[conversation_id] = summary
            return summary

        try:
            # Prepare conversation text for summarization
            conversation_text = self._format_conversation_for_summary(messages)

            # Get summarization prompt
            system_prompt = prompt_loader.get_conversation_summarization_prompt()

            # Generate summary using GenAI
            genai_client = GenAI(system_instruction=system_prompt)
            summary_text = genai_client.generate_text(
                content=f"Summarize this conversation:\n\n{conversation_text}"
            )

            # Extract participants
            participants = list(set(msg.speaker for msg in messages if msg.speaker is not None))

            # Create summary object
            summary = ConversationSummary(
                summary=summary_text,
                last_updated=datetime.now(timezone.utc),
                message_count=len(messages),
                participants=participants,
            )

            # Store summary
            self._conversation_summaries[conversation_id] = summary

            logger.info(
                f"Generated conversation summary for {conversation_id}: {len(summary_text)} chars"
            )
            return summary

        except Exception as e:
            logger.error(f"Failed to generate conversation summary: {str(e)}")
            # Return basic summary on failure
            summary = ConversationSummary(
                summary=f"Conversation with {len(messages)} messages. Summary generation failed.",
                last_updated=datetime.now(timezone.utc),
                message_count=len(messages),
                participants=[],
            )
            self._conversation_summaries[conversation_id] = summary
            return summary

    def _format_conversation_for_summary(self, messages: List[Message]) -> str:
        """
        Format conversation messages for summarization.

        Args:
            messages: List of conversation messages

        Returns:
            Formatted conversation text
        """
        formatted_lines = []

        for msg in messages:
            timestamp = msg.timestamp.strftime("%H:%M")
            speaker = f"{msg.speaker}: " if msg.speaker else ""
            formatted_lines.append(f"[{timestamp}] {speaker}{msg.content}")

        return "\n".join(formatted_lines)

    def get_conversation_stats(self) -> Dict[str, Any]:
        """
        Get statistics about managed conversations.

        Returns:
            Dictionary with conversation statistics
        """
        total_conversations = len(self._conversation_messages)
        total_messages = sum(len(msgs) for msgs in self._conversation_messages.values())
        total_summaries = len(self._conversation_summaries)

        return {
            "total_conversations": total_conversations,
            "total_messages": total_messages,
            "total_summaries": total_summaries,
            "message_window_size": self.message_window_size,
        }
