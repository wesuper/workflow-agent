import asyncio
import logging
from abc import ABC, abstractmethod
from typing import Any, Callable, Dict, Optional

logger = logging.getLogger(__name__)

class IMInterface(ABC):
    def __init__(self, platform_name: str, config: Dict[str, Any], on_message_callback: Callable[[Dict[str, Any]], Any]): # Changed to Any for async callback
        """
        Initializes the IM adapter.

        Args:
            platform_name: The name of the IM platform (e.g., "wechat_work", "discord").
            config: Platform-specific configuration.
            on_message_callback: Async callback function to be invoked when a message is received.
                                 The callback should accept a dictionary representing the message.
        """
        self.platform_name = platform_name
        self.config = config
        self.on_message_callback = on_message_callback
        logger.info(f"[{self.platform_name}] IMInterface initialized with config: {config}")

    @abstractmethod
    async def connect(self) -> bool:
        """Connects to the IM platform. Returns True on success, False otherwise."""
        pass

    @abstractmethod
    async def disconnect(self) -> None:
        """Disconnects from the IM platform."""
        pass

    @abstractmethod
    async def send_message(self, recipient_id: str, message_content: str, message_type: str = "text") -> bool:
        """
        Sends a message to a recipient.

        Args:
            recipient_id: The ID of the recipient (user or channel).
            message_content: The content of the message.
            message_type: Type of message (e.g., "text", "image_url"). Defaults to "text".

        Returns:
            True if the message was sent successfully, False otherwise.
        """
        pass

    @abstractmethod
    async def start_listening(self) -> None:
        """Starts listening for incoming messages. This will typically run in a loop or use event handlers."""
        pass

    def _parse_message(self, raw_message: Any) -> Optional[Dict[str, Any]]:
        """
        Parses a raw message from the IM platform into a standardized dictionary format.
        This is a helper method that should be implemented by subclasses if they have platform-specific
        message formats to process before calling self.on_message_callback.

        The standardized format should ideally include:
        {
            "platform": self.platform_name,
            "user_id": "sender_id",
            "user_name": "Sender Name", // Optional
            "chat_id": "chat_or_channel_id",
            "message_id": "unique_message_id",
            "text": "message_text_content",
            "is_private_chat": True/False,
            "is_mention": True/False, // If the agent was mentioned in a group
            "timestamp": "message_timestamp_isoformat"
        }
        Return None if the message should be ignored.
        """
        # Default implementation assumes raw_message is already in the desired format or ignorable
        if isinstance(raw_message, dict) and "text" in raw_message and "user_id" in raw_message:
            # Ensure essential fields are present, even if with default values
            parsed = {
                "platform": self.platform_name,
                "user_name": None, # Default to None if not provided
                "chat_id": raw_message.get("chat_id", raw_message.get("user_id")), # Default chat_id to user_id if not present
                "message_id": None, # Default to None
                "is_private_chat": True, # Assume private if not specified
                "is_mention": False, # Assume not a mention if not specified
                "timestamp": None, # Default to None
                **raw_message # Overlay the raw_message, allowing it to fill/override defaults
            }
            return parsed
        logger.warning(f"[{self.platform_name}] Unparseable or ignorable raw message: {raw_message}")
        return None

    async def _handle_incoming_message(self, raw_message: Any):
        """
        Internal handler that takes a raw message, parses it, and calls the main callback.
        """
        logger.debug(f"[{self.platform_name}] Received raw message: {raw_message}")
        parsed_message = self._parse_message(raw_message)
        if parsed_message:
            logger.debug(f"[{self.platform_name}] Parsed message: {parsed_message}")
            # Ensure on_message_callback is awaited if it's an async function
            # The type hint for on_message_callback should be Callable[..., Awaitable[None]] or similar
            # For now, we assume it's awaitable as per modern async practices.
            await self.on_message_callback(parsed_message)
        else:
            logger.debug(f"[{self.platform_name}] Message discarded after parsing: {raw_message}")
