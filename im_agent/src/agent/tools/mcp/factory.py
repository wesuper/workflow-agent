import logging # Added logging
from typing import Any, Dict, Optional

from .base import AbstractMCPClient
from .mcp_service_handler import MCPServiceHandler
from .dify_client import DifyClient # To be created in the next step

logger = logging.getLogger(__name__) # Added logger

class MCPFactory:
    @staticmethod
    async def get_mcp_client(client_config_entry: Dict[str, Any]) -> Optional[AbstractMCPClient]:
        """
        Factory method to get an MCP client instance based on configuration.

        Args:
            client_config_entry: A dictionary representing a single MCP connection's configuration.
                                 This should include a 'type' field (e.g., "general", "dify")
                                 and a 'client_config' sub-dictionary for the specific client.
                                 Example:
                                 {
                                     "name": "my_dify_connection", // Informational
                                     "type": "dify",
                                     "client_config": { "api_key_env_var": "DIFY_KEY", ... }
                                 }
                                 {
                                     "name": "general_services",
                                     "type": "general",
                                     "client_config": { "mcp_servers_config_path": "...", "whitelist_file_path": "..."}
                                 }
        Returns:
            An initialized MCP client instance or None if not supported or init fails.
        """
        client_type = client_config_entry.get("type", "general") # Default to general MCPServiceHandler
        specific_client_config = client_config_entry.get("client_config", {})
        client_name = client_config_entry.get("name", client_type) # For logging

        logger.info(f"Attempting to get MCP client of type '{client_type}' for connection '{client_name}'.")
        
        client: Optional[AbstractMCPClient] = None

        if client_type == "general":
            client = MCPServiceHandler()
        elif client_type == "dify":
            client = DifyClient()
        # Add other MCP client types here
        # elif client_type == "another_mcp_type":
        #     client = AnotherMCPClientType()
        else:
            logger.error(f"MCP client type '{client_type}' for connection '{client_name}' not supported.")
            return None
        
        if client:
            try:
                # Pass the specific configuration for this client
                initialized_successfully = await client.initialize(specific_client_config)
                if initialized_successfully:
                    logger.info(f"Successfully initialized MCP client for '{client_name}' (type: {client_type}).")
                    return client
                else:
                    logger.error(f"Failed to initialize MCP client for '{client_name}' (type: {client_type}) - initialize returned False.")
                    return None
            except Exception as e:
                logger.error(f"Exception during MCP client initialization for '{client_name}' (type: {client_type}): {e}", exc_info=True)
                return None
        
        return None
