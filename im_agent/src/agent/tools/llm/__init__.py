# __init__.py for LLM tools module
import logging # Keep logging if used by __main__ or other module-level code
import os
import sys # Added sys for if __name__ == "__main__" example

from .base import AbstractLLMClient
from .dummy_llm import DummyLLM
from .openai_adapter import OpenAILLM
from .factory import LLMFactory # Import the new factory

# Remove old get_llm_adapter function and its direct AppSettings dependency if it was here.
# The factory now handles client creation based on config.

__all__ = [
    "AbstractLLMClient",
    "DummyLLM",
    "OpenAILLM",
    "LLMFactory", # Export the factory
]

# Example of how the factory might be used (optional, for testing)
if __name__ == '__main__':
    import asyncio

    logging.basicConfig(level=logging.DEBUG)
    logger = logging.getLogger(__name__) # Define logger for this block

    async def main_test():
        logger.info("Testing LLMFactory...")

        # Test DummyLLM via factory
        dummy_config = {"dummy_setting": "FactoryTest"}
        dummy_client = await LLMFactory.get_llm_client("DummyLLM", dummy_config)
        if dummy_client:
            logger.info("DummyLLM client obtained from factory.")
            success, response = await dummy_client.get_response("Hello Dummy from factory", [])
            if success:
                logger.info(f"DummyLLM response: {response}")
            else:
                logger.error(f"DummyLLM failed: {response}")
            assert success and "FactoryTest" in response
        else:
            logger.error("Failed to get DummyLLM client from factory.")

        # Test OpenAI via factory (will likely fail init without actual API key env var)
        # Ensure the environment variable specified in 'openai_config' (e.g., 'OPENAI_API_KEY') is set
        # if you want to test successful initialization.
        os.environ["TEST_OPENAI_KEY_FACTORY"] = "dummy_placeholder_key" # Placeholder
        openai_config = {
            "api_key_env_var": "TEST_OPENAI_KEY_FACTORY",
            "model_name": "gpt-3.5-turbo"
        }
        openai_client = await LLMFactory.get_llm_client("OpenAI", openai_config)
        if openai_client:
            logger.info("OpenAI client obtained from factory (init may have failed if key is placeholder).")
            # Attempting get_response will show if client is truly functional
            success, response = await openai_client.get_response("Hello OpenAI from factory", [])
            if success:
                logger.info(f"OpenAI response: {response}")
            else:
                logger.warning(f"OpenAI call failed (as expected with placeholder key): {response}")
            # If key was real, you might assert success here.
            # For placeholder, we expect it to fail initialization or the call.
            # The factory should return None if init fails, so openai_client would be None.
            # If init "succeeded" with a bad key, the call itself would fail.
        else:
            logger.warning("Failed to get/initialize OpenAI client from factory (expected with placeholder key).")

        # Clean up env var if set for test
        if "TEST_OPENAI_KEY_FACTORY" in os.environ:
            del os.environ["TEST_OPENAI_KEY_FACTORY"]

    # asyncio.run(main_test()) # Commented out
    logger.info("LLM __init__ test block finished. Uncomment asyncio.run to test factory.")
