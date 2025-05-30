import logging # Added for proper logging
from typing import Any, Dict, Optional

from .base import AbstractRPAClient
from .automator_client import AutomatorRPAClient # Will be created in this task
from .appium_client import AppiumRPAClient     # Will be created in this task
# from ...config import AppSettings # Assuming AppSettings might be needed for global config access
# For now, config is passed directly to initialize, so AppSettings might not be needed here.

logger = logging.getLogger(__name__) # Added logger

class RPAFactory:
    @staticmethod
    async def get_rpa_client(platform: str, config: Dict[str, Any]) -> Optional[AbstractRPAClient]:
        """
        Factory method to get an RPA client instance based on the platform.

        Args:
            platform: The target platform (e.g., "macos", "android").
            config: Platform-specific configuration for the RPA client.
                    This might include Appium server URL, desired capabilities for Appium,
                    or path to rpa_scripts.json for Automator.

        Returns:
            An initialized RPA client instance or None if platform is not supported or init fails.
        """
        client: Optional[AbstractRPAClient] = None
        if platform == "macos":
            client = AutomatorRPAClient()
        elif platform == "android":
            client = AppiumRPAClient()
        # Add other platforms here if needed in the future
        else:
            logger.warning(f"RPA platform '{platform}' not supported.")
            return None

        if client:
            try:
                initialized_successfully = await client.initialize(config)
                if initialized_successfully:
                    logger.info(f"Successfully initialized RPA client for platform '{platform}'.")
                    return client
                else:
                    logger.error(f"Failed to initialize RPA client for platform '{platform}' (initialize returned False).")
                    return None
            except Exception as e:
                logger.error(f"Exception during RPA client initialization for platform '{platform}': {e}", exc_info=True)
                return None
        return None
