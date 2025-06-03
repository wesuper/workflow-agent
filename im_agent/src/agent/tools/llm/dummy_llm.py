import asyncio # Added for async
import logging
from typing import Any, Dict, List, Tuple # Added Tuple

from .base import AbstractLLMClient # Updated to AbstractLLMClient

logger = logging.getLogger(__name__)

class DummyLLM(AbstractLLMClient): # Inherits from AbstractLLMClient
    """
    A dummy LLM implementation for testing purposes.
    """

    def __init__(self):
        self.config: Dict[str, Any] = {}
        logger.info("DummyLLM instance created.")

    async def initialize(self, config: Dict[str, Any]) -> bool: # Made async, returns bool
        """
        Initializes the DummyLLM with its specific configuration.

        Args:
            config: A dictionary containing configuration parameters.
        """
        self.config = config
        logger.info(f"DummyLLM initialized with config: {config}")
        # For DummyLLM, initialization is always considered successful if config is passed.
        return True

    async def get_response(self, prompt: str, conversation_history: List[Dict[str, str]] = None) -> Tuple[bool, str]: # Made async, returns Tuple
        """
        Returns a canned response, echoing parts of the prompt and history.

        Args:
            prompt: The user's current prompt or message.
            conversation_history: A list of previous messages.

        Returns:
            A tuple: (success: bool, response_text: str).
            For DummyLLM, success is always True.
        """
        # Simulate some async behavior if needed, e.g., await asyncio.sleep(0.01)
        await asyncio.sleep(0.01)

        history_len = len(conversation_history) if conversation_history else 0
        response = f"DummyLLM received: '{prompt}'. History length: {history_len}. Config: {self.config.get('dummy_setting', 'Not Set')}"
        logger.debug(f"DummyLLM generating response: {response}")
        return True, response

if __name__ == '__main__':
    logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

    async def test_dummy_llm():
        dummy_config = {"dummy_setting": "TestValue123", "model_name": "dummy-model-001"}
        dummy_llm = DummyLLM()

        init_success = await dummy_llm.initialize(config=dummy_config)
        print(f"DummyLLM Init success: {init_success}")
        assert init_success

        test_prompt = "Hello, Dummy!"
        test_history = [
            {"role": "user", "content": "Previous message from user."},
            {"role": "assistant", "content": "Previous response from assistant."}
        ]

        print(f"\nTest 1: Prompt only")
        success1, response1 = await dummy_llm.get_response(prompt=test_prompt)
        print(f"Success: {success1}, Response: {response1}\n")
        assert success1

        print(f"Test 2: Prompt and history")
        success2, response2 = await dummy_llm.get_response(prompt=test_prompt, conversation_history=test_history)
        print(f"Success: {success2}, Response: {response2}\n")
        assert success2

        # Test with empty config (should still init successfully)
        empty_config_llm = DummyLLM()
        init_empty_success = await empty_config_llm.initialize(config={})
        assert init_empty_success
        success4, response4 = await empty_config_llm.get_response(prompt="Prompt for empty config")
        print(f"Test 4: Empty config response")
        print(f"Success: {success4}, Response: {response4}")
        assert success4
        assert "Not Set" in response4 # Checks default value usage

    # asyncio.run(test_dummy_llm()) # Commented out
    print("\nDummyLLM example usage finished. Uncomment 'asyncio.run(test_dummy_llm())' to run.")
