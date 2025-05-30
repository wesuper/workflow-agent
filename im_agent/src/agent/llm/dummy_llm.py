import logging
from typing import Any, Dict, List

from .base import LLMInterface

logger = logging.getLogger(__name__)

class DummyLLM(LLMInterface):
    """
    A dummy LLM implementation for testing purposes.
    """

    def __init__(self):
        self.config: Dict[str, Any] = {}
        logger.info("DummyLLM instance created.")

    def initialize(self, config: Dict[str, Any]):
        """
        Initializes the DummyLLM with its specific configuration.

        Args:
            config: A dictionary containing configuration parameters.
        """
        self.config = config
        logger.info(f"DummyLLM initialized with config: {config}")

    def get_response(self, prompt: str, conversation_history: List[Dict[str, str]] = None) -> str:
        """
        Returns a canned response, echoing parts of the prompt and history.

        Args:
            prompt: The user's current prompt or message.
            conversation_history: A list of previous messages.

        Returns:
            A dummy response string.
        """
        history_len = len(conversation_history) if conversation_history else 0
        response = f"DummyLLM received: '{prompt}'. History length: {history_len}. Config: {self.config.get('dummy_setting', 'Not Set')}"
        logger.debug(f"DummyLLM generating response: {response}")
        return response

if __name__ == '__main__':
    # Example Usage
    # Ensure agent.utils.logging_config is available or adjust path
    # from agent.utils.logging_config import setup_logging
    # setup_logging(logging.DEBUG)
    
    # If running standalone and utils are not easily accessible, use basicConfig
    logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')


    dummy_config = {"dummy_setting": "TestValue123", "model_name": "dummy-model-001"}
    dummy_llm = DummyLLM()
    dummy_llm.initialize(config=dummy_config)

    test_prompt = "Hello, Dummy!"
    test_history = [
        {"role": "user", "content": "Previous message from user."},
        {"role": "assistant", "content": "Previous response from assistant."}
    ]

    print(f"Test 1: Prompt only")
    response1 = dummy_llm.get_response(prompt=test_prompt)
    print(f"Response 1: {response1}\n")

    print(f"Test 2: Prompt and history")
    response2 = dummy_llm.get_response(prompt=test_prompt, conversation_history=test_history)
    print(f"Response 2: {response2}\n")

    print(f"Test 3: No history")
    response3 = dummy_llm.get_response(prompt="Another prompt")
    print(f"Response 3: {response3}\n")

    # Test with empty config
    empty_config_llm = DummyLLM()
    empty_config_llm.initialize(config={})
    response4 = empty_config_llm.get_response(prompt="Prompt for empty config")
    print(f"Test 4: Empty config response")
    print(f"Response 4: {response4}")
