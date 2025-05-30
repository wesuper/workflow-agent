import asyncio
import json
import logging
import os
import subprocess
import sys
from typing import Any, Dict, List, Optional, Tuple

from .base import AbstractRPAClient, ElementLocator
# Assuming AppSettings is available via a higher-level import if needed,
# but initialize takes a direct config dict.
# from ....config import AppSettings # Example if AppSettings were needed directly

logger = logging.getLogger(__name__)

class AutomatorRPAClient(AbstractRPAClient):
    """
    RPA client for macOS using Automator, AppleScript, and shell scripts.
    """
    def __init__(self):
        self.workflows_map: Dict[str, Dict[str, Any]] = {}
        self.rpa_scripts_path: Optional[str] = None
        # self.app_settings: Optional[AppSettings] = None # If global settings were needed

    async def initialize(self, config: Dict[str, Any]) -> bool:
        """
        Initializes the AutomatorRPAClient.
        'config' should contain 'rpa_scripts_path' for the JSON map of workflows.
        It might also contain 'base_path_for_relative_scripts' if scripts are relative.
        """
        logger.info("Initializing AutomatorRPAClient...")
        # self.app_settings = config.get("app_settings") # If passing the whole AppSettings instance
        
        # The old AutomatorRunner took AppSettings and read automator_workflows_map_path from it.
        # Now, this client gets its specific config directly.
        # The 'config' dict for this client should specify where to find its scripts map.
        # Let's assume config['rpa_scripts_path'] gives the path to a JSON file
        # similar to the old automator_map.json.
        
        self.rpa_scripts_path = config.get("rpa_scripts_path") # e.g., "config/rpa_macos_scripts.json"
        base_path_for_scripts = config.get("base_path_for_scripts", os.getcwd()) # For resolving relative paths in the map

        if not self.rpa_scripts_path:
            logger.warning("'rpa_scripts_path' not provided in config. No Automator workflows will be loaded.")
            return True # Initialization technically succeeded, just no workflows.

        actual_map_path = self.rpa_scripts_path
        if not os.path.isabs(actual_map_path):
            # If AppSettings path resolution logic was available:
            # main_settings_dir = getattr(self.app_settings, '_main_settings_file_dir', os.getcwd())
            # actual_map_path = os.path.join(main_settings_dir, self.rpa_scripts_path)
            # For now, assume it's relative to a known base or CWD if not absolute.
            # A better approach: the caller of factory should resolve this path from global settings.
            actual_map_path = os.path.join(base_path_for_scripts, self.rpa_scripts_path)


        if not os.path.exists(actual_map_path):
            logger.warning(f"RPA scripts map file not found: {actual_map_path}. No workflows will be available.")
            self.workflows_map = {}
            return True 

        try:
            with open(actual_map_path, 'r') as f:
                loaded_map_content = json.load(f)
        except json.JSONDecodeError as e:
            logger.error(f"Error decoding JSON from RPA scripts map {actual_map_path}: {e}")
            self.workflows_map = {}
            return False # Failed to initialize properly
        except Exception as e:
            logger.error(f"Failed to load RPA scripts map {actual_map_path}: {e}")
            self.workflows_map = {}
            return False

        if not isinstance(loaded_map_content, dict):
            logger.error(f"RPA scripts map content is not a dictionary. Path: {actual_map_path}.")
            self.workflows_map = {}
            return False
            
        self.workflows_map = loaded_map_content
        logger.info(f"RPA scripts map loaded successfully from {actual_map_path}. {len(self.workflows_map)} workflows found.")

        valid_workflows: Dict[str, Dict[str, Any]] = {}
        for name, wf_config in self.workflows_map.items():
            if not isinstance(wf_config, dict) or "path" not in wf_config or "type" not in wf_config:
                logger.warning(f"Invalid configuration for workflow '{name}'. Missing 'path' or 'type'. Skipping.")
                continue
            
            wf_config["path"] = os.path.expanduser(os.path.expandvars(wf_config["path"]))
            # If path is relative, it should be relative to where rpa_scripts_path was, or a defined base.
            if not os.path.isabs(wf_config["path"]):
                 wf_config["path"] = os.path.join(os.path.dirname(actual_map_path), wf_config["path"])


            if wf_config["type"] not in ["osascript_command", "osascript_shell"] and not os.path.exists(wf_config["path"]): # Commands don't need existing file path
                logger.warning(f"Path for workflow '{name}' does not exist: {wf_config['path']}. This workflow may fail.")
            
            valid_workflows[name] = wf_config
        
        self.workflows_map = valid_workflows
        logger.info(f"{len(self.workflows_map)} valid Automator workflows configured: {list(self.workflows_map.keys())}")
        return True

    async def shutdown(self) -> None:
        logger.info("AutomatorRPAClient shutdown completed (no-op).")
        pass # Nothing to clean up for subprocess-based execution typically

    async def execute_workflow(self, workflow_id: str, params: Optional[Dict[str, Any]] = None) -> Tuple[bool, str]:
        if sys.platform != "darwin":
            logger.warning("Automator workflows can only be run on macOS (darwin).")
            return False, "Automator workflows are only supported on macOS."

        if workflow_id not in self.workflows_map:
            return False, f"Workflow ID '{workflow_id}' not found in RPA scripts map."

        config = self.workflows_map[workflow_id]
        path = config["path"]
        workflow_type = config.get("type", "workflow").lower()
        timeout = config.get("timeout_seconds", 60)
        
        # The old `run_workflow` took `arguments: Optional[List[str]]`.
        # The new `execute_workflow` takes `params: Optional[Dict[str, Any]]`.
        # We need to decide how to map these. For now, let's assume if params are provided,
        # they are converted to a list of strings. This might need refinement based on how
        # different script types expect arguments.
        arguments: List[str] = []
        if params:
            # Simple conversion: take values and convert to string.
            # This might need to be more sophisticated depending on script needs.
            arguments = [str(v) for v in params.values()] 
            # Or, if keys are also important for some scripts:
            # arguments = [f"{k}={v}" for k, v in params.items()]

        # Check path existence for file-based types
        if workflow_type in ["workflow", "app", "osascript_file", "shell_script"] and not os.path.exists(path):
             return False, f"Workflow file for '{workflow_id}' not found at path: {path}"

        cmd: List[str] = []
        if workflow_type == "workflow":
            cmd = ["automator"]
            if arguments: cmd.extend(["-i", " ".join(arguments)])
            cmd.append(path)
        elif workflow_type == "app":
            cmd = ["open", path]
            if arguments: cmd.extend(["--args"] + arguments)
        elif workflow_type == "osascript_file":
            cmd = ["osascript", path] + arguments
        elif workflow_type == "osascript_command":
            # Arguments for osascript -e are tricky. The command string (path) usually needs to be constructed with them.
            # For now, we won't directly inject params into path for safety.
            # User should ensure 'path' is a fully formed command or use osascript_file.
            cmd = ["osascript", "-e", path]
            if arguments: logger.warning("Arguments for 'osascript_command' are not directly passed to -e. Modify the command in rpa_scripts.json.")
        elif workflow_type == "shell_script":
            if not os.access(path, os.X_OK): cmd = ["/bin/sh", path] + arguments
            else: cmd = [path] + arguments
        elif workflow_type == "osascript_shell":
            shell_command_to_run = path
            if arguments: shell_command_to_run += " " + " ".join([f"'{arg}'" for arg in arguments]) # Basic quoting for safety
            cmd = ["osascript", "-e", f'do shell script "{shell_command_to_run}"']
        else:
            return False, f"Unsupported workflow type '{workflow_type}' for '{workflow_id}'."

        logger.info(f"Running Automator workflow '{workflow_id}' with command: {' '.join(cmd)}")
        
        try:
            # subprocess.run is blocking, so use asyncio.to_thread
            process = await asyncio.to_thread(
                subprocess.run, cmd, capture_output=True, text=True, check=False, timeout=timeout
            )
            success = process.returncode == 0
            output_message = f"Stdout:\n{process.stdout}\nStderr:\n{process.stderr}"
            if not success:
                logger.warning(f"Workflow '{workflow_id}' failed. RC: {process.returncode}. Output:\n{output_message}")
            else:
                logger.info(f"Workflow '{workflow_id}' completed. Output:\n{output_message}")
            return success, output_message
        except subprocess.TimeoutExpired:
            logger.error(f"Workflow '{workflow_id}' timed out after {timeout} seconds.")
            return False, f"Workflow '{workflow_id}' timed out."
        except FileNotFoundError:
            logger.error(f"Command not found for workflow '{workflow_id}'. Main command: {cmd[0]}. Ensure it's installed.")
            return False, f"Command for '{workflow_id}' ({cmd[0]}) not found."
        except Exception as e:
            logger.error(f"Error running workflow '{workflow_id}': {e}", exc_info=True)
            return False, f"An unexpected error occurred: {e}"

    # --- Placeholder implementations for other AbstractRPAClient methods ---
    async def perform_click(self, locator: ElementLocator, timeout: int = 10) -> bool:
        logger.warning("Method perform_click not yet fully implemented for AutomatorRPAClient.")
        return False

    async def send_keys(self, locator: ElementLocator, text: str, timeout: int = 10) -> bool:
        logger.warning("Method send_keys not yet fully implemented for AutomatorRPAClient.")
        return False

    async def find_element(self, locator: ElementLocator, timeout: int = 10) -> Optional[Any]:
        logger.warning("Method find_element not yet fully implemented for AutomatorRPAClient.")
        return None
            
    async def get_text(self, locator: ElementLocator, timeout: int = 10) -> Optional[str]:
        logger.warning("Method get_text not yet fully implemented for AutomatorRPAClient.")
        return None

    async def element_exists(self, locator: ElementLocator, timeout: int = 5) -> bool:
        logger.warning("Method element_exists not yet fully implemented for AutomatorRPAClient.")
        return False

    async def capture_screenshot(self, save_path: str) -> bool:
        logger.info(f"Attempting to capture screenshot to {save_path} using 'screencapture' utility.")
        if sys.platform != "darwin":
            logger.warning("Screenshot capture is only supported on macOS for AutomatorRPAClient.")
            return False
        try:
            # Use a simple command-line screenshot utility available on macOS
            cmd = ["screencapture", "-x", save_path] # -x to suppress sound
            process = await asyncio.to_thread(
                subprocess.run, cmd, capture_output=True, text=True, check=False, timeout=30
            )
            if process.returncode == 0:
                logger.info(f"Screenshot saved to {save_path}")
                return True
            else:
                logger.error(f"Failed to capture screenshot. RC: {process.returncode}. Stderr: {process.stderr}")
                return False
        except Exception as e:
            logger.error(f"Error capturing screenshot: {e}", exc_info=True)
            return False

    async def scroll(self, direction: str, locator: Optional[ElementLocator] = None, distance_percentage: float = 0.5) -> bool:
        logger.warning("Method scroll not yet fully implemented for AutomatorRPAClient.")
        return False

    async def launch_app(self, app_id_or_name: str) -> bool:
        logger.info(f"Attempting to launch app '{app_id_or_name}' using 'open' command.")
        if sys.platform != "darwin":
            logger.warning("Launching apps is only supported on macOS for AutomatorRPAClient.")
            return False
        try:
            cmd = ["open", "-a", app_id_or_name]
            process = await asyncio.to_thread(
                subprocess.run, cmd, capture_output=True, text=True, check=False, timeout=30
            )
            if process.returncode == 0:
                logger.info(f"Application '{app_id_or_name}' launched successfully.")
                return True
            else:
                # Try `open /path/to/app_id_or_name.app` if -a fails
                cmd = ["open", app_id_or_name]
                process = await asyncio.to_thread(
                    subprocess.run, cmd, capture_output=True, text=True, check=False, timeout=30
                )
                if process.returncode == 0:
                    logger.info(f"Application '{app_id_or_name}' launched successfully (path method).")
                    return True
                else:
                    logger.error(f"Failed to launch app '{app_id_or_name}'. RC: {process.returncode}. Stderr: {process.stderr}")
                    return False
        except Exception as e:
            logger.error(f"Error launching app '{app_id_or_name}': {e}", exc_info=True)
            return False

    async def close_app(self, app_id_or_name: str) -> bool:
        logger.info(f"Attempting to close app '{app_id_or_name}' using AppleScript.")
        if sys.platform != "darwin":
            logger.warning("Closing apps is only supported on macOS for AutomatorRPAClient.")
            return False
        try:
            # Construct an AppleScript command to quit the application
            # Need to handle if app_id_or_name is a path like /Applications/AppName.app
            app_name = app_id_or_name
            if app_name.lower().endswith(".app"):
                app_name = os.path.splitext(os.path.basename(app_name))[0]

            applescript_command = f'tell application "{app_name}" to quit'
            cmd = ["osascript", "-e", applescript_command]
            
            process = await asyncio.to_thread(
                subprocess.run, cmd, capture_output=True, text=True, check=False, timeout=30
            )
            # osascript might return 0 even if the app wasn't running or didn't quit gracefully
            # but if it errors (e.g., app not found), returncode will be non-zero.
            if process.returncode == 0:
                logger.info(f"Sent quit command to application '{app_name}'.")
                # Verify if it actually quit is harder; for now, assume success if command runs.
                return True
            else:
                logger.error(f"Failed to send quit command to app '{app_name}'. RC: {process.returncode}. Stderr: {process.stderr}")
                return False
        except Exception as e:
            logger.error(f"Error closing app '{app_name}': {e}", exc_info=True)
            return False
