"""Configuration settings for IM-Agent."""
import json
import importlib.util
import os
import time
import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

class AppSettings:
    """Holds all loaded configurations."""

    def __init__(self):
        self.settings: Dict[str, Any] = {}
        self._whitelist_module = None
        self._whitelist_path: Optional[str] = None
        self._whitelist_last_modified: Optional[float] = None

    def load_config(self, settings_file_path: str) -> None:
        """Loads the main settings file and any referenced configuration files."""
        if not os.path.exists(settings_file_path):
            logger.error(f"Main settings file not found: {settings_file_path}")
            raise FileNotFoundError(f"Main settings file not found: {settings_file_path}")

        try:
            with open(settings_file_path, 'r') as f:
                main_settings = json.load(f)
        except json.JSONDecodeError as e:
            logger.error(f"Error decoding JSON from {settings_file_path}: {e}")
            raise ValueError(f"Error decoding JSON from {settings_file_path}: {e}")

        self.settings = main_settings

        # Load whitelist if path is defined
        self._whitelist_path = self.settings.get("whitelist_file_path")
        if self._whitelist_path:
            if not os.path.isabs(self._whitelist_path):
                # Assume relative to the main settings file's directory if not absolute
                base_dir = os.path.dirname(settings_file_path)
                self._whitelist_path = os.path.join(base_dir, self._whitelist_path)
            self._load_whitelist_module()

        # Load other referenced configs (e.g., mcp_servers_config)
        mcp_config_path = self.settings.get("mcp_servers_config_path")
        if mcp_config_path:
            if not os.path.isabs(mcp_config_path):
                base_dir = os.path.dirname(settings_file_path)
                mcp_config_path = os.path.join(base_dir, mcp_config_path)
            self._load_json_config("mcp_servers", mcp_config_path)

        automator_map_path = self.settings.get("automator_workflows_map_path")
        if automator_map_path:
            if not os.path.isabs(automator_map_path):
                base_dir = os.path.dirname(settings_file_path)
                automator_map_path = os.path.join(base_dir, automator_map_path)
            self._load_json_config("automator_workflows_map", automator_map_path)


    def _load_json_config(self, key: str, file_path: str) -> None:
        """Loads a JSON configuration file into the settings dictionary."""
        if not os.path.exists(file_path):
            logger.warning(f"JSON config file not found: {file_path}. Skipping.")
            self.settings[key] = None # Or an empty dict, depending on desired behavior
            return
        try:
            with open(file_path, 'r') as f:
                self.settings[key] = json.load(f)
            logger.info(f"Successfully loaded JSON config: {file_path} into key '{key}'")
        except json.JSONDecodeError as e:
            logger.error(f"Error decoding JSON from {file_path}: {e}")
            self.settings[key] = None # Or raise error

    def _load_python_module(self, module_name: str, file_path: str) -> Any:
        """Loads a Python file as a module."""
        if not os.path.exists(file_path):
            logger.error(f"Python module file not found: {file_path}")
            raise FileNotFoundError(f"Python module file not found: {file_path}")
        try:
            spec = importlib.util.spec_from_file_location(module_name, file_path)
            if spec is None or spec.loader is None:
                raise ImportError(f"Could not create module spec for {file_path}")
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            logger.info(f"Successfully loaded Python module: {file_path} as {module_name}")
            return module
        except Exception as e:
            logger.error(f"Error loading Python module {module_name} from {file_path}: {e}")
            raise

    def _load_whitelist_module(self) -> None:
        """Loads or reloads the whitelist Python module."""
        if not self._whitelist_path:
            logger.warning("Whitelist path is not set. Cannot load whitelist.")
            self._whitelist_module = None
            return

        try:
            if self._whitelist_module is None:
                self._whitelist_module = self._load_python_module("agent_whitelist", self._whitelist_path)
                self._whitelist_last_modified = os.path.getmtime(self._whitelist_path)
                logger.info(f"Whitelist loaded from {self._whitelist_path}")
            else:
                # Reload if already loaded (for hot-reloading)
                self._whitelist_module = importlib.reload(self._whitelist_module)
                self._whitelist_last_modified = os.path.getmtime(self._whitelist_path)
                logger.info(f"Whitelist reloaded from {self._whitelist_path}")
        except Exception as e:
            logger.error(f"Failed to load or reload whitelist from {self._whitelist_path}: {e}")
            # Keep the old module if reload fails, or set to None if initial load fails
            if self._whitelist_module is None: # if it was an initial load failure
                 self._whitelist_module = None


    def get_whitelist(self) -> List[str]:
        """Returns the whitelist, hot-reloading if necessary."""
        if not self._whitelist_path:
            logger.warning("Whitelist path not configured. Returning empty whitelist.")
            return []
        if not self._whitelist_module: # If initial load failed
            logger.warning("Whitelist module not loaded. Returning empty whitelist.")
            return []

        try:
            current_mtime = os.path.getmtime(self._whitelist_path)
            if self._whitelist_last_modified is None or current_mtime > self._whitelist_last_modified:
                logger.info(f"Whitelist file {self._whitelist_path} has been modified. Reloading.")
                self._load_whitelist_module()
        except FileNotFoundError:
            logger.error(f"Whitelist file {self._whitelist_path} not found during hot-reload check. Returning current whitelist (if any).")
            # Potentially set self._whitelist_module to None here if strict behavior is desired
            return getattr(self._whitelist_module, "ALLOWED_USERS", []) if self._whitelist_module else []
        except Exception as e:
            logger.error(f"Error during whitelist hot-reload check for {self._whitelist_path}: {e}. Returning current whitelist.")
            # Avoid returning a potentially stale whitelist if reload fails catastrophically
            # or if access to ALLOWED_USERS fails.
            return getattr(self._whitelist_module, "ALLOWED_USERS", []) if self._whitelist_module else []


        if self._whitelist_module:
            return getattr(self._whitelist_module, "ALLOWED_USERS", [])
        return []

    def get_config(self, key: str, default: Any = None) -> Any:
        """Gets a specific configuration value."""
        return self.settings.get(key, default)

    def get_llm_config(self) -> Dict[str, Any]:
        """Gets LLM specific configuration."""
        return self.settings.get("llm_config", {})

    def get_im_settings(self, im_client_name: Optional[str] = None) -> Dict[str, Any]:
        """Gets IM specific settings. If im_client_name is provided, returns settings for that client."""
        im_settings_all = self.settings.get("im_settings", {})
        if im_client_name:
            return im_settings_all.get(im_client_name, {})
        return im_settings_all

    def get_mcp_servers_config(self) -> Optional[Dict[str, Any]]:
        """Gets the loaded MCP servers configuration."""
        return self.settings.get("mcp_servers")

    def get_automator_workflows_map(self) -> Optional[Dict[str, Any]]:
        """Gets the loaded automator workflows map."""
        return self.settings.get("automator_workflows_map")

    @property
    def log_level(self) -> str:
        """Gets the configured log level."""
        return self.settings.get("log_level", "INFO").upper()

# Global instance of settings
settings = AppSettings()

# Example usage (optional, for testing within this file)
if __name__ == "__main__":
    # This part is for demonstration and direct testing of this module.
    # In a real application, another module (e.g., main.py) would call load_config.

    # Create dummy config files for testing
    dummy_settings_json_content = {
        "llm_provider": "DummyLLM",
        "llm_config": {
            "api_key_env_var": "DUMMY_API_KEY",
            "model_name": "dummy-model"
        },
        "mcp_servers_config_path": "dummy_mcp_servers.json",
        "whitelist_file_path": "dummy_whitelist.py",
        "automator_workflows_map_path": "dummy_automator_map.json",
        "log_level": "DEBUG",
        "im_settings": {
            "test_client": {"token": "test_token"}
        }
    }
    dummy_whitelist_py_content = """
ALLOWED_USERS = ["user1", "user2"]
print("Dummy whitelist.py executed during import")
"""
    dummy_mcp_json_content = {
        "server1": {"url": "http://localhost:8080", "token": "s1_token"},
        "server2": {"url": "http://localhost:8081", "token": "s2_token"}
    }
    dummy_automator_map_json_content = {
        "workflow1": {"script_path": "scripts/wf1.sh"},
        "workflow2": {"applescript_path": "scripts/wf2.applescript"}
    }

    # Create dummy config directory and files
    config_dir = "temp_config_for_testing"
    os.makedirs(config_dir, exist_ok=True)
    settings_file = os.path.join(config_dir, "settings.json")
    whitelist_file = os.path.join(config_dir, "dummy_whitelist.py")
    mcp_file = os.path.join(config_dir, "dummy_mcp_servers.json")
    automator_map_file = os.path.join(config_dir, "dummy_automator_map.json")


    with open(settings_file, 'w') as f:
        json.dump(dummy_settings_json_content, f, indent=4)
    with open(whitelist_file, 'w') as f:
        f.write(dummy_whitelist_py_content)
    with open(mcp_file, 'w') as f:
        json.dump(dummy_mcp_json_content, f, indent=4)
    with open(automator_map_file, 'w') as f:
        json.dump(dummy_automator_map_json_content, f, indent=4)

    # Setup basic logging for the test
    from agent.utils.logging_config import setup_logging # Assuming this path is correct relative to where this script is run
    setup_logging(logging.DEBUG) # Use DEBUG for verbose output during test

    logger.info(f"Current working directory: {os.getcwd()}")
    logger.info(f"Attempting to load settings from: {os.path.abspath(settings_file)}")

    try:
        settings.load_config(os.path.abspath(settings_file))

        print("\n--- Loaded Settings ---")
        print(f"LLM Provider: {settings.get_config('llm_provider')}")
        print(f"LLM Config: {settings.get_llm_config()}")
        print(f"Log Level: {settings.log_level}")
        print(f"IM Settings for 'test_client': {settings.get_im_settings('test_client')}")
        print(f"All IM Settings: {settings.get_im_settings()}")

        print(f"MCP Servers Config: {settings.get_mcp_servers_config()}")
        print(f"Automator Workflows Map: {settings.get_automator_workflows_map()}")

        print(f"Initial Whitelist: {settings.get_whitelist()}")

        # Test hot-reloading whitelist
        print("\n--- Testing Whitelist Hot-Reload ---")
        # Modify the whitelist file
        time.sleep(1) # Ensure modification time is different
        with open(whitelist_file, 'w') as f:
            f.write('ALLOWED_USERS = ["user1", "user2", "user3_added_hot"]\nprint("Dummy whitelist.py re-executed during import")')

        # On POSIX systems, mtime resolution might be 1 second.
        # Forcing a noticeable delay to ensure mtime changes.
        # In a real scenario, file system events would trigger this.
        # For testing, ensure enough time passes for mtime to be different.
        # If tests are flaky, increase this sleep or touch the file with a more significant delay.
        time.sleep(1.1) # Wait for more than 1 second to ensure mtime is different

        print(f"Whitelist after modification (should reload): {settings.get_whitelist()}")

        # Test reload failure (e.g. syntax error)
        print("\n--- Testing Whitelist Hot-Reload with Syntax Error ---")
        time.sleep(1)
        with open(whitelist_file, 'w') as f:
            f.write('ALLOWED_USERS = ["user1", "user2", "user4_oops_syntax_error"\nprint("Dummy whitelist.py re-executed with error")') # Intentional syntax error
        time.sleep(1.1)

        # The behavior on error is to keep the last known good whitelist
        print(f"Whitelist after syntax error (should be last good one): {settings.get_whitelist()}")


    except Exception as e:
        print(f"An error occurred during the config test: {e}")
    finally:
        # Clean up dummy files and directory
        # os.remove(settings_file)
        # os.remove(whitelist_file)
        # os.remove(mcp_file)
        # os.remove(automator_map_file)
        # os.rmdir(config_dir)
        print(f"\nTest finished. Dummy config files are in {os.path.abspath(config_dir)}")
        print("Please manually delete this directory after inspection.")

# Example of API_KEY, now managed by AppSettings
# API_KEY = "YOUR_API_KEY" # This would be removed or handled via llm_config
# Instead, you'd access it via settings.get_llm_config().get("api_key") or similar
# after loading the configuration.
