import logging

from ..config import AppSettings # Assuming AppSettings is in agent.config
from .base import MCPInterface
from .mcp_service_handler import MCPServiceHandler

logger = logging.getLogger(__name__)

# Global instance of the MCP handler, initialized on first request.
_mcp_handler_instance: MCPInterface | None = None

def get_mcp_handler(app_settings: AppSettings) -> MCPInterface:
    """
    Factory function to get an instance of the MCPServiceHandler.
    Initializes the handler on first call.

    Args:
        app_settings: The application settings object.

    Returns:
        An initialized instance of MCPServiceHandler.
    """
    global _mcp_handler_instance
    if _mcp_handler_instance is None:
        try:
            logger.info("Initializing MCPServiceHandler for the first time.")
            _mcp_handler_instance = MCPServiceHandler(app_settings=app_settings)
            # The initialize method on MCPServiceHandler currently doesn't do much
            # as most setup is in __init__. If it's made to do more, ensure it's called.
            # _mcp_handler_instance.initialize(app_settings=app_settings) # Already called implicitly by constructor or if made explicit
        except Exception as e:
            logger.error(f"Failed to initialize MCPServiceHandler: {e}")
            # Depending on the application's needs, could raise the error,
            # or return a dummy/fallback handler if partial functionality is desired.
            raise RuntimeError(f"Could not initialize MCPServiceHandler: {e}")
    
    return _mcp_handler_instance

if __name__ == '__main__':
    # Example Usage - This requires agent.config and its dependencies to be available.
    # For simplicity, we'll mock AppSettings and use basic logging.
    
    import os
    import json
    from typing import Any, Dict, List, Optional

    logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

    # --- Mocking AppSettings and its dependencies ---
    class MockAppSettings:
        def __init__(self, main_settings_content, mcp_config_path, whitelist_content, mcp_servers_initial_list=None):
            self.settings = main_settings_content
            self.settings["mcp_servers_config_path"] = mcp_config_path
            self._mcp_config_actual_path = mcp_config_path # Path where MCP handler should read/write
            self._whitelist_content = whitelist_content
            
            # Set up a mock main settings file directory attribute if needed by MCPServiceHandler path resolution
            # This is a bit of a hack to simulate the environment MCPServiceHandler expects for relative paths.
            self._main_settings_file_dir = os.path.dirname(os.path.abspath(__file__)) # Or a temp dir

            # Create dummy mcp-servers.json if content is provided
            if self._mcp_config_actual_path:
                os.makedirs(os.path.dirname(self._mcp_config_actual_path), exist_ok=True)
                if mcp_servers_initial_list is not None:
                    with open(self._mcp_config_actual_path, 'w') as f:
                        json.dump(mcp_servers_initial_list, f, indent=4)
                elif os.path.exists(self._mcp_config_actual_path): # Clean up if no content
                    os.remove(self._mcp_config_actual_path)


        def get_config(self, key: str, default: Any = None) -> Any:
            # Special handling for mcp_servers_config_path to ensure it's what MCPServiceHandler expects
            if key == "mcp_servers_config_path":
                # In a real scenario, config.py might make this path absolute.
                # Here, we return the path relative to where the MCP handler might expect `config/mcp-servers.json`
                # For the test, MCPServiceHandler __init__ should correctly use this.
                return self.settings.get(key, default) # Return the stored path for MCP Handler to resolve
            return self.settings.get(key, default)

        def get_whitelist(self) -> List[str]:
            return self._whitelist_content
        
        # This method is part of AppSettings, but MCPServiceHandler now manages its own file.
        # It's here for completeness of the mock.
        def get_mcp_servers_config(self) -> Optional[List[Dict[str, Any]]]:
             if self._mcp_config_actual_path and os.path.exists(self._mcp_config_actual_path):
                try:
                    with open(self._mcp_config_actual_path, 'r') as f:
                        return json.load(f)
                except Exception as e:
                    logger.error(f"Mock AppSettings: Error reading mock MCP config: {e}")
                    return None
             return None


    # --- Test Setup ---
    test_config_dir_factory = "temp_mcp_factory_test_config"
    os.makedirs(test_config_dir_factory, exist_ok=True)
    
    # Path for mcp-servers.json, relative to the location of __file__ or a known base.
    # For the factory test, we'll use a path inside our temp test directory.
    # The key is that MCPServiceHandler needs to correctly interpret this path.
    # If mcp_servers_config_path in settings.json is "config/mcp-servers.json",
    # and settings.json is in "/app/im_agent/", then the absolute path is "/app/im_agent/config/mcp-servers.json".
    # MCPServiceHandler's __init__ path resolution logic needs to be robust.
    # For this test, we provide an absolute path to avoid ambiguity.
    dummy_mcp_servers_file_for_factory = os.path.abspath(os.path.join(test_config_dir_factory, "mcp-servers-factory.json"))

    initial_services = [
        {"name": "FactoryTestService", "url": "http://example.com/test", "method": "GET"}
    ]

    mock_main_settings = {
        "log_level": "DEBUG",
        # "mcp_servers_config_path" will be set by MockAppSettings to dummy_mcp_servers_file_for_factory
    }
    mock_whitelist = ["factory_user"]

    mock_app_settings_instance = MockAppSettings(
        main_settings_content=mock_main_settings,
        mcp_config_path=dummy_mcp_servers_file_for_factory, # Pass the absolute path here
        whitelist_content=mock_whitelist,
        mcp_servers_initial_list=initial_services
    )
    
    # Ensure _main_settings_file_dir is set correctly in the mock if MCPServiceHandler relies on it
    # for resolving relative paths (which it tries to do as a fallback).
    # If mcp_config_path is absolute, this detail is less critical for this specific test.
    mock_app_settings_instance._main_settings_file_dir = os.path.abspath(test_config_dir_factory)


    print("--- Testing MCP Handler Factory ---")
    try:
        mcp_handler_from_factory = get_mcp_handler(mock_app_settings_instance)
        assert isinstance(mcp_handler_from_factory, MCPServiceHandler)
        print("MCPServiceHandler instance created successfully via factory.")
        
        services = mcp_handler_from_factory.list_services()
        print(f"Services from factory-loaded handler: {services}")
        assert "FactoryTestService" in services

        # Test singleton behavior (optional, based on global instance logic)
        # mcp_handler_again = get_mcp_handler(mock_app_settings_instance)
        # assert mcp_handler_again is mcp_handler_from_factory
        # print("Factory returned the same instance (singleton test).")

    except Exception as e:
        print(f"Error during factory test: {e}")
        logger.exception("Factory test failed")


    # Clean up
    print("\n--- Cleaning up factory test files ---")
    try:
        if os.path.exists(dummy_mcp_servers_file_for_factory):
            os.remove(dummy_mcp_servers_file_for_factory)
        if os.path.exists(test_config_dir_factory):
            # Remove other files if any before rmdir
            for item in os.listdir(test_config_dir_factory):
                item_path = os.path.join(test_config_dir_factory, item)
                if os.path.isfile(item_path):
                    os.remove(item_path)
            os.rmdir(test_config_dir_factory)
        logger.info("Cleaned up factory test temporary files.")
    except Exception as e:
        logger.error(f"Error during factory test cleanup: {e}")

    print("\nMCP Factory example usage finished.")
