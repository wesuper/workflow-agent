from abc import ABC, abstractmethod
from typing import Any, Dict, List, Tuple

class AbstractLLMClient(ABC):
    """Abstract interface for Large Language Model clients."""

    @abstractmethod
    async def initialize(self, config: Dict[str, Any]) -> bool:
        """
        Initializes the LLM client with its specific configuration (e.g., API key, model name).
        Returns True on success.
        """
        pass

    @abstractmethod
    async def get_response(self, prompt: str, conversation_history: List[Dict[str, str]]) -> Tuple[bool, str]:
        """
        Gets a response from the LLM.
        'conversation_history' is a list of messages like {"role": "user/assistant", "content": "..."}.
        Returns a tuple: (success: bool, response_text: str).
        response_text contains the LLM's direct response or an error message.
        """
        pass

    # Optional: Add a method for getting embeddings if needed later
    # @abstractmethod
    # async def get_embeddings(self, text_inputs: List[str]) -> Tuple[bool, List[List[float]]]:
    #     pass
