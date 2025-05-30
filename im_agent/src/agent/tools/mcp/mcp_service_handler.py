import asyncio # For asyncio.to_thread
import json
import logging
import os
import requests # Will be used with asyncio.to_thread
from typing import Any, Dict, List, Optional, Tuple # Added Tuple

# Assuming AppSettings is NOT directly used here anymore, config comes from initialize()
# from ....config import AppSettings # This was an example, adjust as needed
from .base import AbstractMCPClient # Updated to AbstractMCPClient

logger = logging.getLogger(__name__)

class MCPServiceHandler(AbstractMCPClient): # Inherits from AbstractMCPClient
    def __init__(self): # Removed app_settings from constructor
        self.services: Dict[str, Dict[str, Any]] = {}
        self.mcp_servers_config_file: Optional[str] = None
        self.whitelist: List[str] = [] # Whitelist will be loaded during initialize
        self.app_settings_ref: Optional[Any] = None # To store AppSettings if needed for whitelist path resolution
        logger.info("MCPServiceHandler instance created. Needs initialization.")


    async def initialize(self, config: Dict[str, Any]) -> bool: # Made async, takes generic config
        """
        Initializes the MCPServiceHandler.
        'config' should contain 'mcp_servers_config_path' and optionally 'whitelist_file_path'.
        It can also contain 'app_settings' for more complex path resolutions if needed.
        """
        logger.info("Initializing MCPServiceHandler...")
        self.app_settings_ref = config.get("app_settings") # Store if passed, for whitelist path

        mcp_config_path_setting = config.get("mcp_servers_config_path")
        if not mcp_config_path_setting:
            logger.warning("'mcp_servers_config_path' not in config. Services will not be loaded/saved.")
            # Allow initialization to succeed, but with no services loaded from file.
            # Dynamic addition might still work in-memory.
        else:
            self.mcp_servers_config_file = self._resolve_path(mcp_config_path_setting, config)
            if self.mcp_servers_config_file:
                if not await asyncio.to_thread(os.path.exists, self.mcp_servers_config_file):
                    logger.warning(f"MCP servers config file '{self.mcp_servers_config_file}' not found. Will attempt to create if services are added.")
                    self.services = {}
                else:
                    await self._load_services_from_file() # Make it async helper
            else:
                logger.warning("MCP servers config file path could not be determined. Services will not be loaded/persisted.")
        
        # Load whitelist
        whitelist_path_setting = config.get("whitelist_file_path")
        if whitelist_path_setting:
            actual_whitelist_path = self._resolve_path(whitelist_path_setting, config)
            if actual_whitelist_path and await asyncio.to_thread(os.path.exists, actual_whitelist_path):
                try:
                    # Whitelist loading is complex (Python module import).
                    # For simplicity in this refactor, let's assume whitelist is a simple JSON list for now,
                    # or this part needs to adapt the AppSettings._load_python_module logic.
                    # Sticking to current AppSettings._load_whitelist_module logic means AppSettings needs to be involved.
                    # If AppSettings is not available, this simplified client can't hot-reload or load .py whitelist.
                    # Fallback: if app_settings_ref is present and has get_whitelist
                    if self.app_settings_ref and hasattr(self.app_settings_ref, 'get_whitelist'):
                         self.whitelist = await asyncio.to_thread(self.app_settings_ref.get_whitelist) # if get_whitelist can be sync
                         logger.info(f"Whitelist loaded via AppSettings reference: {len(self.whitelist)} users.")
                    else: # Try to load as simple JSON list if no AppSettings ref
                        logger.info(f"Attempting to load whitelist from '{actual_whitelist_path}' as JSON list (fallback).")
                        with open(actual_whitelist_path, 'r') as f:
                            self.whitelist = json.load(f)
                        if not isinstance(self.whitelist, list):
                            logger.error(f"Whitelist file {actual_whitelist_path} is not a JSON list.")
                            self.whitelist = []
                        logger.info(f"Whitelist loaded as JSON list: {len(self.whitelist)} users from {actual_whitelist_path}")

                except Exception as e:
                    logger.error(f"Error loading whitelist from {actual_whitelist_path}: {e}", exc_info=True)
                    self.whitelist = []
            else:
                logger.warning(f"Whitelist file not found at '{actual_whitelist_path}'. Whitelist will be empty.")
        else:
            logger.warning("'whitelist_file_path' not in config. Whitelist functionality will be limited/disabled.")

        logger.info("MCPServiceHandler initialized.")
        return True # Assume success unless critical failure above

    def _resolve_path(self, path_setting: str, config: Dict[str, Any]) -> Optional[str]:
        """Helper to resolve paths, prioritizing AppSettings context if available."""
        if os.path.isabs(path_setting):
            return path_setting
        
        # If app_settings was passed and has _main_settings_file_dir (from original AppSettings)
        if self.app_settings_ref and hasattr(self.app_settings_ref, '_main_settings_file_dir'):
            base_dir = getattr(self.app_settings_ref, '_main_settings_file_dir', None)
            if base_dir:
                return os.path.join(base_dir, path_setting)
        
        # Fallback to CWD or a base_path from config if provided
        base_path = config.get("base_path_for_configs", os.getcwd())
        return os.path.join(base_path, path_setting)


    async def _load_services_from_file(self) -> None:
        if not self.mcp_servers_config_file or not await asyncio.to_thread(os.path.exists, self.mcp_servers_config_file):
            logger.info(f"MCP servers config file not found or path not set. Initializing empty services.")
            self.services = {}
            return
        try:
            # Use asyncio.to_thread for sync file I/O
            def read_json_file(path):
                with open(path, 'r') as f:
                    return json.load(f)
            services_list = await asyncio.to_thread(read_json_file, self.mcp_servers_config_file)
            
            temp_services = {}
            if isinstance(services_list, list):
                for service_config in services_list:
                    if isinstance(service_config, dict) and "name" in service_config:
                        temp_services[service_config["name"]] = service_config
                    else:
                        logger.warning(f"Skipping invalid service entry: {service_config}")
            elif isinstance(services_list, dict): # Support old dict format if encountered
                 for name, s_config in services_list.items():
                      if isinstance(s_config, dict):
                           s_config.setdefault("name", name) # Ensure name is part of config
                           temp_services[name] = s_config
            else:
                logger.error(f"MCP servers config content is not a list or dict. Found type: {type(services_list)}")
            self.services = temp_services
            logger.info(f"MCP services loaded from {self.mcp_servers_config_file}. {len(self.services)} services registered.")
        except Exception as e:
            logger.error(f"Error loading MCP services from {self.mcp_servers_config_file}: {e}", exc_info=True)
            self.services = {}

    async def _save_services_to_file(self) -> bool:
        if not self.mcp_servers_config_file:
            logger.warning("MCP servers config file path not set. Cannot save services.")
            return False
        
        try:
            # Ensure directory exists (blocking os.makedirs is fine with to_thread or if it's usually there)
            dir_name = os.path.dirname(self.mcp_servers_config_file)
            if not await asyncio.to_thread(os.path.exists, dir_name):
                await asyncio.to_thread(os.makedirs, dir_name, exist_ok=True)

            services_list_to_save = list(self.services.values())
            
            def write_json_file(path, data):
                with open(path, 'w') as f:
                    json.dump(data, f, indent=4)
            await asyncio.to_thread(write_json_file, self.mcp_servers_config_file, services_list_to_save)
            
            logger.info(f"MCP services saved to {self.mcp_servers_config_file}")
            return True
        except Exception as e:
            logger.error(f"Error saving MCP services to {self.mcp_servers_config_file}: {e}", exc_info=True)
            return False

    async def invoke_service(self, service_name: str, parameters: Dict[str, Any]) -> Tuple[bool, Dict[str, Any]]:
        if service_name not in self.services:
            msg = f"Service '{service_name}' not found."
            logger.error(msg)
            return False, {"error": msg}

        service_config = self.services[service_name]
        url = service_config.get("url")
        method = service_config.get("method", "GET").upper()

        if not url:
            msg = f"URL not configured for service '{service_name}'."
            logger.error(msg)
            return False, {"error": msg}

        headers = service_config.get("headers", {}).copy() # Use a copy
        api_key_env_var = service_config.get("api_key_env_var")
        api_key_header = service_config.get("api_key_header")
        api_key_value_prefix = service_config.get("api_key_value_prefix", "")

        if api_key_env_var and api_key_header:
            api_key = os.environ.get(api_key_env_var)
            if api_key: headers[api_key_header] = f"{api_key_value_prefix}{api_key}"
            else: logger.warning(f"API key env var '{api_key_env_var}' not set for service '{service_name}'.")
        elif "api_key" in service_config and api_key_header:
            headers[api_key_header] = f"{api_key_value_prefix}{service_config['api_key']}"
        
        timeout = service_config.get("timeout_seconds", 30)

        try:
            logger.info(f"Invoking MCP service '{service_name}': {method} {url} with params: {parameters}")
            
            # Use asyncio.to_thread for the blocking requests call
            response = await asyncio.to_thread(
                requests.request, method, url, params=parameters if method == "GET" else None, 
                data=parameters if method == "POST" and headers.get("Content-Type") == "application/x-www-form-urlencoded" else None,
                json=parameters if method == "POST" and headers.get("Content-Type") != "application/x-www-form-urlencoded" else None,
                headers=headers, timeout=timeout
            )
            response.raise_for_status()
            try:
                return True, response.json()
            except json.JSONDecodeError:
                logger.warning(f"Response from '{service_name}' was not JSON. Returning raw text.")
                return True, {"raw_response": response.text}
        except requests.exceptions.Timeout:
            msg = f"Timeout calling service '{service_name}' at {url}."
            logger.error(msg)
            return False, {"error": msg}
        except requests.exceptions.RequestException as e:
            error_details = str(e)
            if e.response is not None:
                error_details += f" | Status: {e.response.status_code} | Response: {e.response.text[:200]}"
            logger.error(f"Error calling service '{service_name}': {error_details}", exc_info=True)
            return False, {"error": f"Request failed: {error_details}"}
        except Exception as e:
            logger.error(f"Unexpected error invoking '{service_name}': {e}", exc_info=True)
            return False, {"error": f"Unexpected error: {e}"}

    async def add_service(self, service_config: Dict[str, Any], user_id: str) -> bool:
        if user_id not in self.whitelist: # Use the loaded whitelist
            logger.warning(f"User '{user_id}' not whitelisted. Denying add_service for '{service_config.get('name')}'.")
            return False

        required_keys = ["name", "url", "method"]
        if not all(key in service_config for key in required_keys):
            logger.error(f"Invalid service_config: missing required keys. Config: {service_config}")
            return False
        
        service_name = service_config["name"]
        if service_name in self.services:
            logger.warning(f"Service '{service_name}' already exists.")
            return False

        self.services[service_name] = service_config
        logger.info(f"Service '{service_name}' added to in-memory registry by user '{user_id}'.")
        
        if not await self._save_services_to_file():
            logger.error(f"Failed to persist new service '{service_name}' to file. It will be lost on restart.")
            # Optionally revert: del self.services[service_name]
            return False # Consider this a failure if persistence fails
        return True

    async def list_services(self) -> List[Dict[str, Any]]:
        # Return a list of service configuration dictionaries
        return list(self.services.values())

# Note: The __main__ block from the original MCPServiceHandler is removed as it relied on AppSettings
# and a more complex setup. Testing should be done via the factory or dedicated test scripts.
