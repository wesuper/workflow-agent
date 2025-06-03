import asyncio
import logging
import os
from typing import Any, Dict, List, Tuple

from openai import OpenAI, APIError # Assuming the OpenAI library is available
from .base import AbstractLLMClient # Updated to AbstractLLMClient

logger = logging.getLogger(__name__)

class OpenAILLM(AbstractLLMClient): # Inherits from AbstractLLMClient
    """
    LLM adapter for OpenAI's API.
    """

    def __init__(self):
        self.client: OpenAI | None = None
        self.config: Dict[str, Any] = {}
        logger.info("OpenAILLM instance created.")

    async def initialize(self, config: Dict[str, Any]) -> bool: # Made async, returns bool
        """
        Initializes the OpenAI LLM adapter.

        Args:
            config: A dictionary containing configuration parameters such as:
                    - 'api_key_env_var': Name of the environment variable for the API key.
                    - 'api_key': Direct API key (optional, overrides env var).
                    - 'model_name': The model to use (e.g., "gpt-3.5-turbo").
                    - Other OpenAI client parameters (e.g., 'base_url', 'timeout').
        """
        self.config = config
        api_key = None

        if 'api_key' in config and config['api_key']:
            api_key = config['api_key']
            logger.info("Using API key directly from config.")
        elif 'api_key_env_var' in config and config['api_key_env_var']:
            api_key = os.environ.get(config['api_key_env_var'])
            if api_key:
                logger.info(f"Using API key from environment variable: {config['api_key_env_var']}.")
            else:
                logger.error(f"Environment variable {config['api_key_env_var']} not found for API key.")
                return False # Initialization failed
        else:
            logger.warning("No API key or API key environment variable specified in config.")
            return False # Initialization failed

        if api_key:
            try:
                # OpenAI client instantiation is synchronous
                client_args = {k: v for k, v in config.items() if k not in ['api_key_env_var', 'model_name', 'llm_provider']}
                # Wrap synchronous client creation in to_thread if it's potentially blocking
                # For OpenAI client, it's usually quick, but for consistency with other blocking calls:
                self.client = await asyncio.to_thread(OpenAI, api_key=api_key, **client_args)
                logger.info(f"OpenAI client initialized successfully with model: {self.config.get('model_name', 'default')}.")
                return True
            except Exception as e:
                logger.error(f"Failed to initialize OpenAI client: {e}", exc_info=True)
                self.client = None
                return False
        else:
            logger.warning("OpenAI client not initialized due to missing API key.")
            return False


    async def get_response(self, prompt: str, conversation_history: List[Dict[str, str]] = None) -> Tuple[bool, str]: # Made async, returns Tuple
        """
        Gets a response from the OpenAI API.

        Args:
            prompt: The user's current prompt or message.
            conversation_history: A list of previous messages.

        Returns:
            A tuple: (success: bool, response_text: str).
            response_text contains the LLM's direct response or an error message.
        """
        if not self.client:
            logger.error("OpenAI client is not initialized. Cannot get response.")
            return False, "Error: OpenAI client is not initialized. Please check API key and configuration."

        messages = []
        if conversation_history:
            messages.extend(conversation_history)
        messages.append({"role": "user", "content": prompt})

        model_name = self.config.get("model_name", "gpt-3.5-turbo")

        try:
            logger.debug(f"Sending request to OpenAI API with model: {model_name}, messages: {messages}")

            # The chat.completions.create call is blocking
            completion = await asyncio.to_thread(
                self.client.chat.completions.create,
                model=model_name,
                messages=messages
            )

            response_content = completion.choices[0].message.content
            logger.info("Received response from OpenAI API.")
            logger.debug(f"OpenAI API full response: {completion}")
            return True, response_content.strip() if response_content else ""
        except APIError as e:
            logger.error(f"OpenAI API error: {e}", exc_info=True)
            return False, f"Error: OpenAI API request failed: {e}"
        except Exception as e:
            logger.error(f"An unexpected error occurred while calling OpenAI API: {e}", exc_info=True)
            return False, f"Error: An unexpected error occurred: {e}"

if __name__ == '__main__':
    logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

    async def test_openai_adapter():
        # Scenario 1: API key from environment variable (requires actual key for real test)
        print("--- Scenario 1: API key from environment variable ---")
        os.environ["MY_TEST_OPENAI_KEY"] = "YOUR_OPENAI_API_KEY_HERE" # Replace with a real key for live test

        if os.environ["MY_TEST_OPENAI_KEY"] == "YOUR_OPENAI_API_KEY_HERE":
            logger.warning("Using placeholder API key for MY_TEST_OPENAI_KEY. Real API calls will fail or use other credentials if available.")

        openai_config_env = {
            "api_key_env_var": "MY_TEST_OPENAI_KEY",
            "model_name": "gpt-3.5-turbo"
        }

        openai_llm_env = OpenAILLM()
        init_success = await openai_llm_env.initialize(config=openai_config_env)
        print(f"Init success (env key): {init_success}")

        if init_success:
            print("\nTesting get_response (env key):")
            success, response_env = await openai_llm_env.get_response(prompt="Hello, what is the capital of France?")
            print(f"Call success: {success}, Response: {response_env}")
        else:
            # Try get_response even if init failed to see the error message
            success, response_env_fail = await openai_llm_env.get_response(prompt="This should fail due to init.")
            print(f"Call success after failed init: {success}, Response: {response_env_fail}")

        # Scenario 2: Missing API key
        print("\n--- Scenario 2: Missing API key ---")
        openai_config_missing = {"model_name": "gpt-3.5-turbo"}
        openai_llm_missing = OpenAILLM()
        init_success_missing = await openai_llm_missing.initialize(config=openai_config_missing)
        print(f"Init success (missing key): {init_success_missing}")
        assert not init_success_missing # Expecting init to fail

        success_missing, response_missing = await openai_llm_missing.get_response(prompt="What is 2+2?")
        print(f"Call success (missing key): {success_missing}, Response: {response_missing}")
        assert not success_missing
        assert "client is not initialized" in response_missing

    # asyncio.run(test_openai_adapter()) # Commented out to prevent auto-execution in some environments
    print("\nOpenAI Adapter example usage finished. Uncomment 'asyncio.run(test_openai_adapter())' to run.")
