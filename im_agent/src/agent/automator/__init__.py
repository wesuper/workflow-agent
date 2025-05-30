import logging
import sys
from typing import Optional

from ..config import AppSettings # Assuming AppSettings is in agent.config
from .runner import AutomatorRunner

logger = logging.getLogger(__name__)

_automator_runner_instance: Optional[AutomatorRunner] = None

def get_automator_runner(app_settings: AppSettings) -> Optional[AutomatorRunner]:
    """
    Factory function to get an instance of the AutomatorRunner.
    Initializes the runner on the first call if on macOS.
    Returns None if not on macOS.

    Args:
        app_settings: The application settings object.

    Returns:
        An initialized instance of AutomatorRunner if on macOS, otherwise None.
    """
    global _automator_runner_instance

    if sys.platform != "darwin":
        if _automator_runner_instance is None: # Log only once
            logger.info("AutomatorRunner is only available on macOS (darwin). Will not initialize on this platform.")
            # Optionally, create a dummy runner that always fails or warns
            # For now, returning None means the feature is disabled.
        _automator_runner_instance = None # Ensure it stays None
        return None

    if _automator_runner_instance is None:
        try:
            logger.info("Initializing AutomatorRunner for the first time on macOS.")
            _automator_runner_instance = AutomatorRunner(app_settings=app_settings)
        except Exception as e:
            logger.error(f"Failed to initialize AutomatorRunner: {e}", exc_info=True)
            # In case of error, don't keep a partially initialized instance.
            _automator_runner_instance = None 
            # Depending on application needs, could raise error or return None to indicate failure.
            # For now, returning None on init failure.
            return None 
            # raise RuntimeError(f"Could not initialize AutomatorRunner: {e}")
    
    return _automator_runner_instance

if __name__ == '__main__':
    # Example Usage - This requires agent.config and its dependencies.
    # For simplicity, we'll mock AppSettings and use basic logging.
    import os
    import json
    from typing import Any, Dict

    logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

    # --- Mock AppSettings ---
    class MockAppSettings:
        def __init__(self, settings_data: Dict[str, Any], main_config_dir: Optional[str] = None):
            self.settings = settings_data
            # Used by AutomatorRunner to resolve relative paths for the map if needed
            self._main_settings_file_dir = main_config_dir or os.getcwd() 

        def get_config(self, key: str, default: Any = None) -> Any:
            return self.settings.get(key, default)

        def get_automator_workflows_map(self) -> Optional[Dict[str, Any]]:
            # This mock attempts to load from path if specified, or returns direct content
            map_data_or_path = self.settings.get("automator_workflows_map")
            
            if isinstance(map_data_or_path, str): # It's a path
                path = map_data_or_path
                if not os.path.isabs(path):
                    path = os.path.join(self._main_settings_file_dir, path)
                
                if os.path.exists(path):
                    try:
                        with open(path, 'r') as f:
                            return json.load(f)
                    except json.JSONDecodeError as e:
                        logger.error(f"MockAppSettings: Failed to decode JSON from {path}: {e}")
                        return None
                    except Exception as e:
                        logger.error(f"MockAppSettings: Error loading map from {path}: {e}")
                        return None
                else:
                    logger.warning(f"MockAppSettings: Automator map file path does not exist: {path}")
                    return None
            # If it's not a string, assume it's the already loaded map content (dict) or None
            elif isinstance(map_data_or_path, dict) or map_data_or_path is None:
                return map_data_or_path
            else:
                logger.error(f"MockAppSettings: Unexpected type for 'automator_workflows_map': {type(map_data_or_path)}")
                return None


    # --- Test Setup ---
    test_config_dir_factory = "temp_automator_factory_test_config"
    os.makedirs(test_config_dir_factory, exist_ok=True)
    
    # Create a dummy automator_map.json for the factory test
    dummy_map_path = os.path.join(test_config_dir_factory, "automator_map_factory.json")
    dummy_map_content = {
        "factory_test_workflow": {
            "path": "echo 'Factory test workflow executed'", 
            "type": "osascript_shell", # Use a type that can be easily faked/tested
            "description": "A test workflow for the factory."
        }
    }
    with open(dummy_map_path, 'w') as f:
        json.dump(dummy_map_content, f)

    mock_main_settings = {
        "log_level": "DEBUG",
        "automator_workflows_map_path": dummy_map_path # Path to the map
        # "automator_workflows_map": dummy_map_content # Alternative: pass content directly
    }

    mock_app_settings_instance = MockAppSettings(
        settings_data=mock_main_settings,
        main_config_dir=os.path.abspath(test_config_dir_factory) # So it can find dummy_map_path if relative
    )
    
    # For the mock AppSettings to correctly load the map via path, ensure the path is correctly handled by it.
    # If `automator_workflows_map_path` is relative, `main_config_dir` in MockAppSettings becomes important.
    # If it's absolute, then it's simpler. Let's make dummy_map_path absolute for clarity in test.
    mock_app_settings_instance.settings["automator_workflows_map_path"] = os.path.abspath(dummy_map_path)


    print("--- Testing Automator Runner Factory ---")
    try:
        runner_from_factory = get_automator_runner(mock_app_settings_instance)
        
        if sys.platform == "darwin":
            assert runner_from_factory is not None
            assert isinstance(runner_from_factory, AutomatorRunner)
            print("AutomatorRunner instance created successfully via factory on macOS.")
            
            workflows = runner_from_factory.list_available_workflows()
            print(f"Workflows from factory-loaded runner: {workflows}")
            assert "factory_test_workflow" in workflows

            # Test singleton behavior
            runner_again = get_automator_runner(mock_app_settings_instance)
            assert runner_again is runner_from_factory # Should return the same instance
            print("Factory returned the same instance (singleton test).")

        else:
            assert runner_from_factory is None
            print("AutomatorRunner factory correctly returned None on non-macOS platform.")

    except Exception as e:
        print(f"Error during factory test: {e}")
        logger.exception("Factory test failed")

    # Clean up
    print("\n--- Cleaning up factory test files ---")
    try:
        if os.path.exists(dummy_map_path):
            os.remove(dummy_map_path)
        if os.path.exists(test_config_dir_factory):
            os.rmdir(test_config_dir_factory)
        logger.info("Cleaned up factory test temporary files.")
    except Exception as e:
        logger.error(f"Error during factory test cleanup: {e}")

    print("\nAutomator Factory example usage finished.")
