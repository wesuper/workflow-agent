import logging
import os
from typing import Any, Dict, List

from openai import OpenAI, APIError # Assuming the OpenAI library is available
from .base import LLMInterface

logger = logging.getLogger(__name__)

class OpenAILLM(LLMInterface):
    """
    LLM adapter for OpenAI's API.
    """

    def __init__(self):
        self.client: OpenAI | None = None
        self.config: Dict[str, Any] = {}
        logger.info("OpenAILLM instance created.")

    def initialize(self, config: Dict[str, Any]):
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
                # raise ValueError(f"API key environment variable {config['api_key_env_var']} not set.")
                # Not raising error here to allow for testing other parts if key is missing
                # The get_response will fail if client is not initialized.
        else:
            logger.warning("No API key or API key environment variable specified in config.")
            # Not raising error here to allow for testing other parts if key is missing

        if api_key:
            try:
                client_args = {k: v for k, v in config.items() if k not in ['api_key_env_var', 'model_name', 'llm_provider']}
                self.client = OpenAI(api_key=api_key, **client_args)
                logger.info(f"OpenAI client initialized successfully with model: {self.config.get('model_name', 'default')}.")
            except Exception as e:
                logger.error(f"Failed to initialize OpenAI client: {e}")
                self.client = None # Ensure client is None if initialization fails
        else:
            logger.warning("OpenAI client not initialized due to missing API key.")


    def get_response(self, prompt: str, conversation_history: List[Dict[str, str]] = None) -> str:
        """
        Gets a response from the OpenAI API.

        Args:
            prompt: The user's current prompt or message.
            conversation_history: A list of previous messages.

        Returns:
            The LLM's response as a string, or an error message if the API call fails.
        """
        if not self.client:
            logger.error("OpenAI client is not initialized. Cannot get response.")
            return "Error: OpenAI client is not initialized. Please check API key and configuration."

        messages = []
        if conversation_history:
            messages.extend(conversation_history)
        messages.append({"role": "user", "content": prompt})

        model_name = self.config.get("model_name", "gpt-3.5-turbo") # Default model

        try:
            logger.debug(f"Sending request to OpenAI API with model: {model_name}, messages: {messages}")
            completion = self.client.chat.completions.create(
                model=model_name,
                messages=messages
            )
            response_content = completion.choices[0].message.content
            logger.info("Received response from OpenAI API.")
            logger.debug(f"OpenAI API full response: {completion}")
            return response_content.strip() if response_content else ""
        except APIError as e:
            logger.error(f"OpenAI API error: {e}")
            return f"Error: OpenAI API request failed: {e}"
        except Exception as e:
            logger.error(f"An unexpected error occurred while calling OpenAI API: {e}")
            return f"Error: An unexpected error occurred: {e}"

if __name__ == '__main__':
    # Example Usage
    # This requires the `openai` package and an API key.
    # Set OPENAI_API_KEY environment variable or put in config.

    # from agent.utils.logging_config import setup_logging
    # setup_logging(logging.DEBUG) # Assuming this path is correct
    logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')


    # Scenario 1: API key from environment variable
    print("--- Scenario 1: API key from environment variable ---")
    os.environ["MY_TEST_OPENAI_KEY"] = "your_actual_openai_api_key_if_testing_live" # Replace with a real key for live test
    
    if os.environ.get("MY_TEST_OPENAI_KEY") == "your_actual_openai_api_key_if_testing_live" and \
       "your_actual_openai_api_key_if_testing_live" == "your_actual_openai_api_key_if_testing_live": # Quick check if placeholder is still there
        logger.warning("Using placeholder API key for MY_TEST_OPENAI_KEY. Real API calls will fail.")
        # To prevent accidental real calls during non-focused testing, you might skip parts of the test:
        # skip_live_calls = True
    
    # skip_live_calls = False # Set to True if you don't want to make real calls or key is placeholder

    openai_config_env = {
        "api_key_env_var": "MY_TEST_OPENAI_KEY",
        "model_name": "gpt-3.5-turbo"
        # "timeout": 20 # example of another OpenAI client parameter
    }
    
    openai_llm_env = OpenAILLM()
    openai_llm_env.initialize(config=openai_config_env)

    # Test get_response (will only work if API key is valid and set)
    # if not skip_live_calls and openai_llm_env.client:
    # print("\nTesting get_response (requires valid API key):")
    # response_env = openai_llm_env.get_response(prompt="Hello, what is the capital of France?")
    # print(f"Response from OpenAI (env key): {response_env}")
    # else:
    # print("\nSkipping get_response test for env key scenario (API key likely placeholder or not set for live test).")
    # Simulate a call to see the error message if client isn't initialized
    if not openai_llm_env.client:
        print("\nTesting get_response with uninitialized client (env key scenario):")
        response_env_fail = openai_llm_env.get_response(prompt="This should fail.")
        print(f"Response (should be error): {response_env_fail}")


    # Scenario 2: API key directly in config
    print("\n--- Scenario 2: API key directly in config ---")
    openai_config_direct = {
        "api_key": "another_dummy_key_or_real_one_for_testing", # Replace if testing live
        "model_name": "gpt-3.5-turbo"
    }
    if openai_config_direct["api_key"] == "another_dummy_key_or_real_one_for_testing":
        logger.warning("Using placeholder API key for direct config. Real API calls will fail.")
    
    openai_llm_direct = OpenAILLM()
    openai_llm_direct.initialize(config=openai_config_direct)
    # if not skip_live_calls and openai_llm_direct.client:
    # print("\nTesting get_response (requires valid API key):")
    # response_direct = openai_llm_direct.get_response(prompt="Tell me a joke.")
    # print(f"Response from OpenAI (direct key): {response_direct}")
    # else:
    # print("\nSkipping get_response test for direct key scenario (API key likely placeholder or not set for live test).")
    if not openai_llm_direct.client:
        print("\nTesting get_response with uninitialized client (direct key scenario):")
        response_direct_fail = openai_llm_direct.get_response(prompt="This should also fail.")
        print(f"Response (should be error): {response_direct_fail}")


    # Scenario 3: Missing API key
    print("\n--- Scenario 3: Missing API key ---")
    openai_config_missing = {
        "model_name": "gpt-3.5-turbo"
    }
    openai_llm_missing = OpenAILLM()
    openai_llm_missing.initialize(config=openai_config_missing)
    print("\nTesting get_response with missing API key:")
    response_missing = openai_llm_missing.get_response(prompt="What is 2+2?")
    print(f"Response (missing key): {response_missing}")

    # Scenario 4: Invalid API key (if client initializes but API returns error)
    # This would require a key that is syntactically valid but not authorized by OpenAI.
    # For this example, we'll assume that if the key is bad, the APIError will be caught.
    print("\n--- Scenario 4: Potentially invalid API key (example) ---")
    # Assuming a key that might be rejected by OpenAI
    openai_config_invalid_key = {
        "api_key": "sk-thisisnotarealkeythisisnotarealkeythisisnotarealkey",
        "model_name": "gpt-3.5-turbo"
    }
    openai_llm_invalid = OpenAILLM()
    openai_llm_invalid.initialize(config=openai_config_invalid_key)
    # if not skip_live_calls and openai_llm_invalid.client: # client might initialize
    # print("\nTesting get_response with potentially invalid API key:")
    # response_invalid = openai_llm_invalid.get_response(prompt="What is your name?")
    # print(f"Response (invalid key): {response_invalid}") # Expected to be an API error
    # else:
    # print("\nSkipping get_response test for invalid key scenario.")
    # If the key is just a placeholder, it might not even attempt a call if client init fails
    # or if it's an obviously malformed key.
    # The current dummy key "sk-thisisnotarealkey..." might be rejected by the client library before an API call.
    # If the client *does* initialize, then the get_response will attempt the call.
    if openai_llm_invalid.client:
         print("\nTesting get_response with potentially invalid API key (client initialized):")
         response_invalid = openai_llm_invalid.get_response(prompt="What is your name?")
         print(f"Response (invalid key): {response_invalid}")
    else:
        print("\nClient did not initialize with the 'invalid' key, likely due to format validation.")
        response_invalid_fail = openai_llm_invalid.get_response(prompt="This should fail.")
        print(f"Response (should be error): {response_invalid_fail}")


    # Test with conversation history
    # if not skip_live_calls and openai_llm_env.client: # Using the env one if it was set up with a real key
    # print("\n--- Testing with conversation history ---")
    #     history = [
    # {"role": "user", "content": "My name is Bob."},
    # {"role": "assistant", "content": "Nice to meet you Bob!"}
    # ]
    #     response_hist = openai_llm_env.get_response(prompt="Do you remember my name?", conversation_history=history)
    # print(f"Response with history: {response_hist}")
    # else:
    # print("\nSkipping conversation history test.")

    print("\nOpenAI Adapter example usage finished.")
