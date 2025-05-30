import json
import logging
import os
import requests # type: ignore
from typing import Any, Dict, List, Optional

from ..config import AppSettings # Assuming AppSettings is in agent.config
from .base import MCPInterface

logger = logging.getLogger(__name__)

class MCPServiceHandler(MCPInterface):
    def __init__(self, app_settings: AppSettings):
        self.app_settings = app_settings
        self.services: Dict[str, Dict[str, Any]] = {}
        self.mcp_servers_config_file: Optional[str] = None
        
        # Determine the absolute path for mcp-servers.json
        mcp_config_path_setting = self.app_settings.get_config("mcp_servers_config_path")
        
        if not mcp_config_path_setting:
            logger.warning("mcp_servers_config_path not set in settings. MCP services will not be loaded or saved.")
            # Services will remain empty, operations like add_service might still work in-memory if not for persistence
            return 

        if os.path.isabs(mcp_config_path_setting):
            self.mcp_servers_config_file = mcp_config_path_setting
        else:
            # Assuming settings_file_path was stored or can be retrieved if relative path logic is complex
            # For now, let's assume if relative, it's relative to a known CWD or a base config directory.
            # If AppSettings stores the path of the main settings file, use its dirname.
            # This part might need refinement based on how AppSettings resolves relative paths for other files.
            # Let's assume for now AppSettings.get_config("mcp_servers_config_path") *could* return an absolute path
            # if it was processed by AppSettings.load_config to be absolute.
            # Or, if settings.py itself knows where the root config dir is.
            # For this implementation, we'll assume the path from settings is either absolute
            # or relative to where the app is run, which is less robust.
            # A better approach is for AppSettings to provide the absolute path.
            
            # Let's try to get it from the loaded settings if it was pre-processed by AppSettings
            loaded_mcp_config = self.app_settings.get_mcp_servers_config()
            if loaded_mcp_config is not None and isinstance(self.app_settings.settings.get("mcp_servers"), str) :
                # This implies that get_mcp_servers_config() might not be what we need for the *path*,
                # but rather the content if it was already loaded by config.py's _load_json_config.
                # This design needs careful consideration.
                # For now, let's assume mcp_servers_config_path IS the path.
                # If it was relative, AppSettings should have made it absolute during its load_config.
                # We'll rely on the path provided by AppSettings.
                # This requires AppSettings.get_config("mcp_servers_config_path") to return the *path*
                # and AppSettings.get_mcp_servers_config() to return the *content*.
                # The initial thinking for config.py was that it would load these.
                # Let's adjust: MCPServiceHandler will manage its own file.
                
                # Path to the main settings file (if available, to resolve relative paths)
                # This information is not directly available in AppSettings in the current design.
                # Fallback to CWD for relative paths if no better base path is known.
                # This is a potential point of failure if CWD is not the project root.
                # A robust solution: app_settings should store its own root path.
                
                # Simplification: Assume AppSettings.get_config("mcp_servers_config_path") returns a usable path.
                # And if it was relative in settings.json, it was made absolute by config.py.
                # This is not currently what config.py does for mcp_servers_config_path, it stores it as is.
                # This means we need to resolve it relative to the main settings file path.
                # This is a gap. For now, let's use a placeholder for base_dir
                # A better way: Pass the base_dir of the main config file to MCPServiceHandler or have AppSettings resolve it.
                main_settings_file_dir = getattr(self.app_settings, '_main_settings_file_dir', os.getcwd()) # Hacky
                self.mcp_servers_config_file = os.path.join(main_settings_file_dir, mcp_config_path_setting)
                logger.info(f"Relative mcp_servers_config_path '{mcp_config_path_setting}' resolved to '{self.mcp_servers_config_file}' relative to main settings dir.")

        if self.mcp_servers_config_file:
             # Check if the file exists before trying to load. If not, it's fine, it might be created later.
            if not os.path.exists(self.mcp_servers_config_file):
                logger.warning(f"MCP servers config file '{self.mcp_servers_config_file}' not found. Will attempt to create if services are added.")
                # Initialize with an empty list structure if file doesn't exist, so _save_services_to_file works correctly
                self.services = {} # Services are stored as a dict internally
            else:
                self.load_services_from_file()
        else:
            logger.warning("MCP servers configuration file path could not be determined. Services will not be loaded or persisted.")


    def initialize(self, app_settings: AppSettings):
        """
        Initializes the MCP handler. In this implementation, most initialization
        is done in __init__ as it needs app_settings early.
        This method can be used for any post-__init__ setup if necessary.
        """
        # If app_settings were not passed to __init__, this would be the place to set them up.
        # self.app_settings = app_settings
        # self.load_services_from_file()
        logger.info("MCPServiceHandler initialized. Whitelist and services loaded (if available).")


    def load_services_from_file(self) -> None:
        if not self.mcp_servers_config_file:
            logger.warning("MCP servers config file path not set. Cannot load services.")
            return

        if not os.path.exists(self.mcp_servers_config_file):
            logger.info(f"MCP servers config file not found: {self.mcp_servers_config_file}. Initializing with empty services list.")
            self.services = {}
            return

        try:
            with open(self.mcp_servers_config_file, 'r') as f:
                services_list = json.load(f)
            
            # Convert list of services to a dictionary keyed by service name
            self.services = {}
            if isinstance(services_list, list): # Ensure it's a list as per example
                for service_config in services_list:
                    if isinstance(service_config, dict) and "name" in service_config:
                        self.services[service_config["name"]] = service_config
                    else:
                        logger.warning(f"Skipping invalid service entry in {self.mcp_servers_config_file}: {service_config}")
                logger.info(f"MCP services loaded successfully from {self.mcp_servers_config_file}. {len(self.services)} services registered.")
            else:
                # Handle the case where the file might contain a dict (old format from a previous thought process)
                # Or if it's just malformed. For now, assume it should be a list.
                logger.error(f"MCP servers config file {self.mcp_servers_config_file} is not a list of services. Found type: {type(services_list)}")
                self.services = {}


        except json.JSONDecodeError as e:
            logger.error(f"Error decoding JSON from {self.mcp_servers_config_file}: {e}")
            self.services = {} # Initialize empty on error
        except Exception as e:
            logger.error(f"An unexpected error occurred while loading MCP services from {self.mcp_servers_config_file}: {e}")
            self.services = {}


    def _save_services_to_file(self) -> bool:
        if not self.mcp_servers_config_file:
            logger.warning("MCP servers config file path not set. Cannot save services.")
            return False
        
        # Ensure the directory exists
        try:
            os.makedirs(os.path.dirname(self.mcp_servers_config_file), exist_ok=True)
        except Exception as e:
            logger.error(f"Could not create directory for MCP config file {self.mcp_servers_config_file}: {e}")
            return False

        # Convert internal dictionary back to list for saving, matching example format
        services_list_to_save = list(self.services.values())

        try:
            with open(self.mcp_servers_config_file, 'w') as f:
                json.dump(services_list_to_save, f, indent=4)
            logger.info(f"MCP services saved successfully to {self.mcp_servers_config_file}")
            return True
        except Exception as e:
            logger.error(f"Error saving MCP services to {self.mcp_servers_config_file}: {e}")
            return False

    def invoke_service(self, service_name: str, parameters: Dict[str, Any]) -> Dict[str, Any]:
        if service_name not in self.services:
            logger.error(f"Service '{service_name}' not found.")
            return {"error": f"Service '{service_name}' not found."}

        service_config = self.services[service_name]
        url = service_config.get("url")
        method = service_config.get("method", "GET").upper()

        if not url:
            logger.error(f"URL not configured for service '{service_name}'.")
            return {"error": f"URL not configured for service '{service_name}'."}

        headers = service_config.get("headers", {})
        
        # Handle API key if configured
        api_key_env_var = service_config.get("api_key_env_var")
        api_key_header = service_config.get("api_key_header") # e.g. "Authorization"
        api_key_value_prefix = service_config.get("api_key_value_prefix", "") # e.g. "Bearer "

        if api_key_env_var and api_key_header:
            api_key = os.environ.get(api_key_env_var)
            if not api_key:
                logger.warning(f"API key environment variable '{api_key_env_var}' not set for service '{service_name}'.")
                # Depending on policy, could return error or proceed without auth
            else:
                headers[api_key_header] = f"{api_key_value_prefix}{api_key}"
        elif "api_key" in service_config and api_key_header: # Direct API key in config
            headers[api_key_header] = f"{api_key_value_prefix}{service_config['api_key']}"


        try:
            logger.info(f"Invoking MCP service '{service_name}': {method} {url} with params: {parameters}")
            if method == "GET":
                response = requests.get(url, params=parameters, headers=headers, timeout=service_config.get("timeout_seconds", 30))
            elif method == "POST":
                if headers.get("Content-Type", "").lower() == "application/x-www-form-urlencoded":
                    response = requests.post(url, data=parameters, headers=headers, timeout=service_config.get("timeout_seconds", 30))
                else: # Default to JSON
                    response = requests.post(url, json=parameters, headers=headers, timeout=service_config.get("timeout_seconds", 30))
            # Add other methods like PUT, DELETE as needed
            else:
                logger.error(f"Unsupported HTTP method '{method}' for service '{service_name}'.")
                return {"error": f"Unsupported HTTP method '{method}'."}

            response.raise_for_status()  # Raise an exception for bad status codes (4xx or 5xx)
            
            # Try to parse JSON, but return raw text if it fails (e.g. for non-JSON APIs)
            try:
                return response.json()
            except json.JSONDecodeError:
                logger.warning(f"Response from service '{service_name}' was not valid JSON. Returning raw text.")
                return {"raw_response": response.text}

        except requests.exceptions.Timeout:
            logger.error(f"Timeout while calling service '{service_name}' at {url}.")
            return {"error": "Request timed out."}
        except requests.exceptions.RequestException as e:
            logger.error(f"Error calling service '{service_name}' at {url}: {e}")
            # Attempt to get more details from the response if available
            error_details = str(e)
            if e.response is not None:
                error_details += f" | Status Code: {e.response.status_code} | Response: {e.response.text[:200]}" # Truncate long responses
            return {"error": f"Request failed: {error_details}"}
        except Exception as e:
            logger.error(f"An unexpected error occurred during service invocation for '{service_name}': {e}")
            return {"error": f"An unexpected error occurred: {e}"}


    def add_service(self, service_config: Dict[str, Any], user_id: str) -> bool:
        whitelist = self.app_settings.get_whitelist()
        if user_id not in whitelist:
            logger.warning(f"User '{user_id}' not in whitelist. Denying add_service for '{service_config.get('name')}'.")
            return False

        # Validate service_config
        required_keys = ["name", "url", "method"]
        for key in required_keys:
            if key not in service_config:
                logger.error(f"Invalid service_config: missing required key '{key}'. Config: {service_config}")
                return False
        
        service_name = service_config["name"]
        if service_name in self.services:
            logger.warning(f"Service '{service_name}' already exists. Use update_service or remove first.")
            # Or decide to overwrite: self.services[service_name] = service_config
            return False # For now, don't overwrite

        self.services[service_name] = service_config
        logger.info(f"Service '{service_name}' added to registry by user '{user_id}'.")
        
        if not self._save_services_to_file():
            # If save fails, should we revert the in-memory addition?
            # For now, it remains in memory but won't persist.
            logger.error(f"Failed to persist new service '{service_name}' to file. It will be lost on restart.")
            # Optionally, remove from self.services here if strict persistence is required for it to be "added".
            # del self.services[service_name]
            # return False
        return True

    def list_services(self) -> List[str]:
        return list(self.services.keys())


if __name__ == '__main__':
    # This example usage requires a bit more setup due to AppSettings dependency.
    # We'll mock AppSettings and create dummy config files.
    
    logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

    # --- Mocking AppSettings and its dependencies ---
    class MockAppSettings:
        def __init__(self, main_settings_content, mcp_config_path, whitelist_content, mcp_servers_content=None):
            self.settings = main_settings_content
            self.settings["mcp_servers_config_path"] = mcp_config_path # Ensure this key is present
            self._mcp_config_path = mcp_config_path # Store the intended path
            self._whitelist_content = whitelist_content # Store whitelist directly
            self._mcp_servers_content_on_load = mcp_servers_content # Content to be "loaded" by MCP handler

            # Create dummy mcp-servers.json if content is provided
            if self._mcp_servers_content_on_load is not None and self._mcp_config_path:
                # Ensure directory exists
                os.makedirs(os.path.dirname(self._mcp_config_path), exist_ok=True)
                with open(self._mcp_config_path, 'w') as f:
                    json.dump(self._mcp_servers_content_on_load, f, indent=4)
            elif self._mcp_config_path and os.path.exists(self._mcp_config_path): # cleanup if no content
                os.remove(self._mcp_config_path)


        def get_config(self, key: str, default: Any = None) -> Any:
            return self.settings.get(key, default)

        def get_whitelist(self) -> List[str]:
            return self._whitelist_content
        
        # MCPServiceHandler now manages its own file, so this isn't strictly used by it for loading
        # but might be used by other parts of an app.
        def get_mcp_servers_config(self) -> Optional[Dict[str, Any]]:
            if self._mcp_config_path and os.path.exists(self._mcp_config_path):
                try:
                    with open(self._mcp_config_path, 'r') as f:
                        return json.load(f) # Returns list based on example
                except:
                    return None
            return self._mcp_servers_content_on_load # Fallback to initial content if file ops fail

    # --- Test Setup ---
    # Create a temporary directory for config files
    test_config_dir = "temp_mcp_test_config"
    os.makedirs(test_config_dir, exist_ok=True)
    
    dummy_mcp_servers_path = os.path.join(test_config_dir, "mcp-servers.json")
    
    initial_mcp_services_list = [
        {
            "name": "EchoService",
            "description": "Echoes back parameters.",
            "url": "https://httpbin.org/anything", # httpbin is great for testing
            "method": "POST",
            "params": {"message": "string"},
            "auth_type": "none"
        },
        {
            "name": "GetIP",
            "description": "Gets the client IP.",
            "url": "https://httpbin.org/ip",
            "method": "GET",
            "auth_type": "none"
        }
    ]

    main_settings = {
        "log_level": "DEBUG",
        # mcp_servers_config_path is set by MockAppSettings constructor
    }
    whitelist = ["user_admin", "user_test"]

    # Create MockAppSettings instance
    # This will also create the dummy_mcp_servers_path file with initial_mcp_services_list
    mock_settings = MockAppSettings(
        main_settings_content=main_settings,
        mcp_config_path=dummy_mcp_servers_path,
        whitelist_content=whitelist,
        mcp_servers_content=initial_mcp_services_list
    )
    
    # Initialize MCPServiceHandler
    mcp_handler = MCPServiceHandler(app_settings=mock_settings)
    mcp_handler.initialize(app_settings=mock_settings) # Call initialize as per typical pattern

    print("--- Initial Services ---")
    print(f"Services loaded: {mcp_handler.list_services()}")
    assert "EchoService" in mcp_handler.list_services()
    assert "GetIP" in mcp_handler.list_services()

    print("\n--- Invoking EchoService ---")
    echo_params = {"text_to_echo": "Hello MCP!", "number": 123}
    response = mcp_handler.invoke_service("EchoService", echo_params)
    print(f"EchoService response: {json.dumps(response, indent=2)}")
    assert response.get("json", {}).get("text_to_echo") == "Hello MCP!"

    print("\n--- Invoking GetIP ---")
    ip_response = mcp_handler.invoke_service("GetIP", {})
    print(f"GetIP response: {json.dumps(ip_response, indent=2)}")
    assert "origin" in ip_response # httpbin /ip returns origin

    print("\n--- Adding a new service (by whitelisted user) ---")
    new_service_config_valid = {
        "name": "NewPostService",
        "url": "https://httpbin.org/post",
        "method": "POST",
        "description": "A new service for posting data."
    }
    add_success = mcp_handler.add_service(new_service_config_valid, user_id="user_admin")
    print(f"Add service 'NewPostService' success: {add_success}")
    assert add_success
    assert "NewPostService" in mcp_handler.list_services()
    
    # Verify persistence by reloading (optional, or check file content)
    mcp_handler_reloaded = MCPServiceHandler(app_settings=mock_settings) # Re-init with same settings
    assert "NewPostService" in mcp_handler_reloaded.list_services(), "Service should persist after save and reload"


    print("\n--- Attempting to add service (by non-whitelisted user) ---")
    new_service_config_unauth = {
        "name": "UnauthorizedService",
        "url": "https://httpbin.org/status/200",
        "method": "GET"
    }
    add_fail_auth = mcp_handler.add_service(new_service_config_unauth, user_id="user_unknown")
    print(f"Add service 'UnauthorizedService' success: {add_fail_auth}")
    assert not add_fail_auth
    assert "UnauthorizedService" not in mcp_handler.list_services()

    print("\n--- Attempting to add service (invalid config) ---")
    new_service_config_invalid = {
        "name": "InvalidService",
        # Missing 'url' and 'method'
    }
    add_fail_invalid = mcp_handler.add_service(new_service_config_invalid, user_id="user_admin")
    print(f"Add service 'InvalidService' success: {add_fail_invalid}")
    assert not add_fail_invalid
    assert "InvalidService" not in mcp_handler.list_services()

    print("\n--- Invoking non-existent service ---")
    non_existent_response = mcp_handler.invoke_service("FakeService", {})
    print(f"FakeService response: {json.dumps(non_existent_response, indent=2)}")
    assert "error" in non_existent_response
    
    print("\n--- Test with API Key Auth (dummy, using httpbin headers echo) ---")
    os.environ["TEST_MCP_APIKEY"] = "test_secret_key_123"
    authed_service_config = {
        "name": "AuthedService",
        "url": "https://httpbin.org/headers", # This endpoint echoes headers
        "method": "GET",
        "description": "A service that needs an API key.",
        "api_key_env_var": "TEST_MCP_APIKEY",
        "api_key_header": "X-Api-Key",
        "api_key_value_prefix": "TestPrefix " # With a space
    }
    add_auth_service_success = mcp_handler.add_service(authed_service_config, "user_admin")
    assert add_auth_service_success
    auth_response = mcp_handler.invoke_service("AuthedService", {})
    print(f"AuthedService response: {json.dumps(auth_response, indent=2)}")
    assert auth_response.get("headers", {}).get("X-Api-Key") == "TestPrefix test_secret_key_123"


    # Clean up dummy files and directory
    print("\n--- Cleaning up ---")
    try:
        if os.path.exists(dummy_mcp_servers_path):
            os.remove(dummy_mcp_servers_path)
        if os.path.exists(test_config_dir):
            os.rmdir(test_config_dir) # rmdir only if empty, remove files first if any other were created
        logger.info("Cleaned up temporary test files.")
    except Exception as e:
        logger.error(f"Error during cleanup: {e}")

    print("\nMCPServiceHandler example usage finished.")
