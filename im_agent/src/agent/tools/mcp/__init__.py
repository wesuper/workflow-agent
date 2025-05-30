# __init__.py for MCP tools module
import logging # Keep logging if used by __main__ or other module-level code
import os 
import sys 
import json # For example usage
from typing import Any, Dict, List, Optional # For example usage

from .base import AbstractMCPClient
from .mcp_service_handler import MCPServiceHandler
from .dify_client import DifyClient # Will be created
from .factory import MCPFactory   # Import the new factory

# Remove old get_mcp_handler function if it was here.
# The factory now handles client creation.

__all__ = [
    "AbstractMCPClient",
    "MCPServiceHandler",
    "DifyClient",
    "MCPFactory", # Export the factory
]

# Example of how the factory might be used (optional, for testing)
if __name__ == '__main__':
    import asyncio

    logging.basicConfig(level=logging.DEBUG)
    logger = logging.getLogger(__name__) # Define logger for this block

    # Mock AppSettings or provide necessary paths directly for testing MCP clients
    # This example focuses on the factory, assuming configs are correctly structured.

    async def main_test():
        logger.info("Testing MCPFactory...")

        # 1. Test MCPServiceHandler via factory
        # Create a dummy mcp-servers.json and whitelist.json for MCPServiceHandler
        test_config_dir = "temp_mcp_factory_main_test"
        os.makedirs(test_config_dir, exist_ok=True)
        
        dummy_mcp_servers_file = os.path.join(test_config_dir, "mcp-servers.json")
        with open(dummy_mcp_servers_file, 'w') as f:
            json.dump([{"name": "TestEcho", "url": "https://httpbin.org/anything", "method": "GET"}], f)
            
        dummy_whitelist_file = os.path.join(test_config_dir, "whitelist.json") # Using .json for test simplicity
        with open(dummy_whitelist_file, 'w') as f:
            json.dump(["user1", "admin"], f)

        general_mcp_config_entry = {
            "name": "my_general_services",
            "type": "general",
            "client_config": {
                "mcp_servers_config_path": dummy_mcp_servers_file, # Relative to where this test is run, or use absolute
                "whitelist_file_path": dummy_whitelist_file,       # Relative or absolute
                "base_path_for_configs": os.path.abspath(test_config_dir) # To help resolve above if relative
            }
        }
        # Adjust paths to be absolute for robustness in test if needed
        general_mcp_config_entry["client_config"]["mcp_servers_config_path"] = os.path.abspath(dummy_mcp_servers_file)
        general_mcp_config_entry["client_config"]["whitelist_file_path"] = os.path.abspath(dummy_whitelist_file)


        mcp_handler_client = await MCPFactory.get_mcp_client(general_mcp_config_entry)
        if mcp_handler_client:
            logger.info("MCPServiceHandler client obtained from factory.")
            services = await mcp_handler_client.list_services()
            logger.info(f"MCPServiceHandler services: {services}")
            assert any(s['name'] == 'TestEcho' for s in services)
            
            success, response = await mcp_handler_client.invoke_service("TestEcho", {"param": "value"})
            logger.info(f"TestEcho Invocation: Success={success}, Response={response}")
            assert success
        else:
            logger.error("Failed to get MCPServiceHandler client from factory.")

        # 2. Test DifyClient via factory (will fail API calls without real key/setup)
        # Ensure DIFY_API_KEY_TEST_FACTORY is set in your environment for this test to attempt init
        os.environ["DIFY_API_KEY_TEST_FACTORY"] = "dummy_dify_api_key_for_testing"
        dify_mcp_config_entry = {
            "name": "my_dify_services",
            "type": "dify",
            "client_config": {
                "api_key_env_var": "DIFY_API_KEY_TEST_FACTORY",
                "api_base_url": "https://api.dify.ai/v1", # Example, use actual if testing live
                "apps": [
                    {"name": "test_dify_chat_app", "app_id": "app-123", "description": "Test Dify Chat", "features": ["chat"]},
                ]
            }
        }
        dify_client = await MCPFactory.get_mcp_client(dify_mcp_config_entry)
        if dify_client:
            logger.info("DifyClient obtained from factory.")
            dify_apps = await dify_client.list_services()
            logger.info(f"Dify configured apps: {dify_apps}")
            assert any(app['name'] == 'test_dify_chat_app' for app in dify_apps)
            
            # This call will likely fail because the API key is a dummy and endpoint might not be real
            success, response = await dify_client.invoke_service("test_dify_chat_app", {"query": "Hello Dify", "user_id": "test_user"})
            logger.info(f"Dify App Invocation: Success={success}, Response={response}")
            assert not success # Expecting failure with dummy key
        else:
            logger.error("Failed to get DifyClient from factory.")
        
        if "DIFY_API_KEY_TEST_FACTORY" in os.environ:
            del os.environ["DIFY_API_KEY_TEST_FACTORY"]

        # Cleanup dummy files
        if os.path.exists(dummy_mcp_servers_file): os.remove(dummy_mcp_servers_file)
        if os.path.exists(dummy_whitelist_file): os.remove(dummy_whitelist_file)
        if os.path.exists(test_config_dir): os.rmdir(test_config_dir)


    # asyncio.run(main_test()) # Commented out
    logger.info("MCP __init__ test block finished. Uncomment asyncio.run to test factory.")
