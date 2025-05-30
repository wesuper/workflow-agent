from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional

class MemoryInterface(ABC):
    """Abstract interface for agent memory operations."""

    @abstractmethod
    async def get_short_term_memory(self, conversation_id: str, max_messages: Optional[int] = None) -> List[Dict[str, str]]:
        """Retrieves short-term memory (e.g., conversation history)."""
        pass

    @abstractmethod
    async def add_to_short_term_memory(self, conversation_id: str, message: Dict[str, str]) -> None:
        """Adds a message to short-term memory."""
        pass

    @abstractmethod
    async def clear_short_term_memory(self, conversation_id: str) -> None:
        """Clears short-term memory for a conversation."""
        pass

    @abstractmethod
    async def get_long_term_memory(self, user_id: str, key: str) -> Optional[Any]:
        """Retrieves a value from long-term memory for a user."""
        pass

    @abstractmethod
    async def set_long_term_memory(self, user_id: str, key: str, value: Any) -> None:
        """Sets a value in long-term memory for a user."""
        pass
            
    @abstractmethod
    async def delete_long_term_memory(self, user_id: str, key: str) -> bool:
        """Deletes a value from long-term memory. Returns True if key existed and was deleted."""
        pass
