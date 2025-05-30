from abc import ABC, abstractmethod
from typing import Any, Dict, List

class LLMInterface(ABC):
    @abstractmethod
    def initialize(self, config: Dict[str, Any]):
        """
        Initializes the LLM adapter with its specific configuration.

        Args:
            config: A dictionary containing configuration parameters for this LLM
                    (e.g., api_key, model_name, endpoint_url).
        """
        pass

    @abstractmethod
    def get_response(self, prompt: str, conversation_history: List[Dict[str, str]] = None) -> str:
        """
        Gets a response from the LLM.

        Args:
            prompt: The user's current prompt or message.
            conversation_history: A list of previous messages, where each message
                                  is a dictionary like {"role": "user/assistant", "content": "message text"}.
                                  Optional, defaults to None for no history.

        Returns:
            The LLM's response as a string.
        """
        pass
