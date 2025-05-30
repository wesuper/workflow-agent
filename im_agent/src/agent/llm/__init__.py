import logging

from ..config import AppSettings # Assuming AppSettings is in agent.config
from .base import LLMInterface
from .dummy_llm import DummyLLM
from .openai_adapter import OpenAILLM

logger = logging.getLogger(__name__)

# Maps provider names to their respective classes
SUPPORTED_LLM_PROVIDERS = {
    "DummyLLM": DummyLLM,
    "OpenAI": OpenAILLM,
    # Future LLM providers can be added here
}

def get_llm_adapter(app_settings: AppSettings) -> LLMInterface:
    """
    Factory function to get an initialized LLM adapter based on application settings.

    Args:
        app_settings: The application settings object which contains the
                      configuration for the LLM provider and its specific settings.

    Returns:
        An initialized instance of a class that implements LLMInterface.

    Raises:
        ValueError: If the configured LLM provider is not supported or
                    if the LLM configuration is missing.
    """
    llm_provider_name = app_settings.get_config("llm_provider")
    if not llm_provider_name:
        logger.error("LLM provider name is not configured in settings.")
        raise ValueError("LLM provider ('llm_provider') not specified in settings.")

    llm_config = app_settings.get_llm_config()
    if not llm_config:
        logger.error(f"LLM configuration ('llm_config') not found for provider: {llm_provider_name}.")
        raise ValueError(f"LLM configuration ('llm_config') not found for provider: {llm_provider_name}.")

    if llm_provider_name not in SUPPORTED_LLM_PROVIDERS:
        logger.error(f"Unsupported LLM provider: {llm_provider_name}. Supported are: {list(SUPPORTED_LLM_PROVIDERS.keys())}")
        raise ValueError(f"Unsupported LLM provider: {llm_provider_name}. Supported are: {list(SUPPORTED_LLM_PROVIDERS.keys())}")

    llm_class = SUPPORTED_LLM_PROVIDERS[llm_provider_name]
    
    try:
        adapter_instance = llm_class()
        adapter_instance.initialize(config=llm_config)
        logger.info(f"Successfully initialized LLM adapter for provider: {llm_provider_name}")
        return adapter_instance
    except Exception as e:
        logger.error(f"Error initializing LLM adapter for {llm_provider_name}: {e}")
        # Depending on desired strictness, could re-raise or return a default/dummy
        raise RuntimeError(f"Failed to initialize LLM adapter {llm_provider_name}: {e}")


if __name__ == '__main__':
    # Example Usage - This requires agent.config and agent.utils.logging_config to be accessible
    # For simplicity, we'll mock AppSettings and use basic logging.
    
    logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

    # Mock AppSettings class for this example
    class MockAppSettings:
        def __init__(self, provider, config):
            self._provider = provider
            self._config = config

        def get_config(self, key: str, default=None):
            if key == "llm_provider":
                return self._provider
            return default

        def get_llm_config(self):
            return self._config

    # Test with DummyLLM
    print("--- Testing with DummyLLM ---")
    dummy_settings_data = {"dummy_setting": "Hello from Dummy Config"}
    mock_app_settings_dummy = MockAppSettings(provider="DummyLLM", config=dummy_settings_data)
    
    try:
        dummy_adapter = get_llm_adapter(mock_app_settings_dummy)
        response = dummy_adapter.get_response("Test prompt for Dummy")
        print(f"DummyLLM Response: {response}")
        assert "Hello from Dummy Config" in response 
    except Exception as e:
        print(f"Error with DummyLLM: {e}")


    # Test with OpenAI (will show initialization logs, actual calls would need API key)
    print("\n--- Testing with OpenAI (Initialization) ---")
    # Ensure your environment variable (e.g., OPENAI_API_KEY) is set if you want to test live calls
    # For this test, we'll just check initialization.
    os.environ["MY_TEST_OPENAI_KEY_FOR_INIT"] = "dummy_key_for_init_test" # Dummy key for init test
    openai_settings_data = {
        "api_key_env_var": "MY_TEST_OPENAI_KEY_FOR_INIT",
        "model_name": "gpt-3.5-turbo-test"
    }
    mock_app_settings_openai = MockAppSettings(provider="OpenAI", config=openai_settings_data)

    try:
        openai_adapter = get_llm_adapter(mock_app_settings_openai)
        # The following line would make an API call if the key were real and client initialized properly
        # For now, it will likely return an error or a message indicating the client isn't fully working.
        response_openai = openai_adapter.get_response("Test prompt for OpenAI")
        print(f"OpenAI Response (may be error if key is dummy): {response_openai}")
    except Exception as e:
        print(f"Error with OpenAI: {e}")

    # Test with an unsupported provider
    print("\n--- Testing with UnsupportedLLM ---")
    mock_app_settings_unsupported = MockAppSettings(provider="UnsupportedLLM", config={})
    try:
        unsupported_adapter = get_llm_adapter(mock_app_settings_unsupported)
    except ValueError as e:
        print(f"Correctly caught error for unsupported LLM: {e}")
    except Exception as e:
        print(f"Unexpected error for unsupported LLM: {e}")

    # Test with missing llm_provider
    print("\n--- Testing with missing llm_provider ---")
    mock_app_settings_missing_provider = MockAppSettings(provider=None, config={})
    try:
        missing_provider_adapter = get_llm_adapter(mock_app_settings_missing_provider)
    except ValueError as e:
        print(f"Correctly caught error for missing LLM provider: {e}")
    except Exception as e:
        print(f"Unexpected error for missing LLM provider: {e}")
        
    # Test with missing llm_config
    print("\n--- Testing with missing llm_config ---")
    mock_app_settings_missing_config = MockAppSettings(provider="DummyLLM", config=None)
    try:
        missing_config_adapter = get_llm_adapter(mock_app_settings_missing_config)
    except ValueError as e:
        print(f"Correctly caught error for missing LLM config: {e}")
    except Exception as e:
        print(f"Unexpected error for missing LLM config: {e}")

    print("\nLLM Factory example usage finished.")
