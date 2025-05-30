import logging # Added logging
from typing import Any, Dict, Optional

from .base import AbstractLLMClient
from .openai_adapter import OpenAILLM
from .dummy_llm import DummyLLM
# from ....config import AppSettings # If AppSettings were needed globally by the factory

logger = logging.getLogger(__name__) # Added logger

SUPPORTED_LLM_PROVIDERS = {
    "OpenAI": OpenAILLM,
    "DummyLLM": DummyLLM,
}

class LLMFactory:
    @staticmethod
    async def get_llm_client(provider_name: str, config: Dict[str, Any]) -> Optional[AbstractLLMClient]:
        """
        Factory method to get an LLM client instance.

        Args:
            provider_name: Name of the LLM provider (e.g., "OpenAI", "DummyLLM").
            config: LLM-specific configuration. This dictionary is passed directly
                    to the client's initialize method.

        Returns:
            An initialized LLM client instance or None if not supported or init fails.
        """
        logger.info(f"Attempting to get LLM client for provider: {provider_name}")
        LLMClientClass = SUPPORTED_LLM_PROVIDERS.get(provider_name)
        
        if not LLMClientClass:
            logger.error(f"LLM provider '{provider_name}' not supported.")
            return None
        
        client = LLMClientClass()
        try:
            initialized_successfully = await client.initialize(config)
            if initialized_successfully:
                logger.info(f"Successfully initialized LLM client for '{provider_name}'.")
                return client
            else:
                logger.error(f"Failed to initialize LLM client for '{provider_name}' (initialize returned False).")
                return None
        except Exception as e:
            logger.error(f"Exception during LLM client initialization for '{provider_name}': {e}", exc_info=True)
            return None
