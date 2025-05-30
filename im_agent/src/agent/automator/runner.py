import json
import logging
import os
import subprocess
import sys
from typing import Any, Dict, List, Optional, Tuple

# Assuming AppSettings is in agent.config, adjust if necessary
# from ..config import AppSettings 

logger = logging.getLogger(__name__)

class AutomatorRunner:
    def __init__(self, app_settings: Any): # app_settings should be AppSettings type
        self.app_settings = app_settings
        self.workflows_map: Dict[str, Dict[str, Any]] = {}
        self._load_workflows_map()

    def _load_workflows_map(self) -> None:
        map_path_setting = self.app_settings.get_config("automator_workflows_map_path")
        if not map_path_setting:
            logger.warning("'automator_workflows_map_path' not set in AppSettings. AutomatorRunner will have no workflows.")
            return

        # Resolve path similar to how MCPServiceHandler or config.py might do it.
        # This assumes AppSettings can provide a base directory or the path is absolute.
        # For now, let's assume the path from settings is either absolute or resolve it carefully.
        
        # A simple approach: if path is not absolute, assume it's relative to a 'config' dir in CWD,
        # or better, relative to the main settings file's directory.
        # This path resolution should ideally be centralized or handled consistently by AppSettings.
        
        # Let's assume AppSettings.get_config returns a path that AppSettings itself has already resolved to be absolute,
        # or that it's relative to a known base path that AppSettings can provide.
        # If app_settings has a record of the main config file's directory:
        # base_dir = getattr(self.app_settings, '_main_settings_file_dir', os.getcwd())
        # actual_map_path = map_path_setting
        # if not os.path.isabs(actual_map_path):
        #    actual_map_path = os.path.join(base_dir, actual_map_path)
        
        # Simpler: Use the path directly as loaded by AppSettings.get_automator_workflows_map() which should be the content
        # The path itself is AppSettings.get_config("automator_workflows_map_path")
        # The content is AppSettings.get_automator_workflows_map()
        
        # The content of the map is already loaded by config.py's _load_json_config
        loaded_map_content = self.app_settings.get_automator_workflows_map()

        if loaded_map_content is None:
            # This means config.py couldn't load it (e.g. file not found at the path specified in settings.json)
            actual_map_path = map_path_setting # For logging purposes
            if not os.path.isabs(actual_map_path):
                # Attempt to construct a full path for logging if main_settings_file_dir is known
                 main_settings_file_dir = getattr(self.app_settings, '_main_settings_file_dir', None)
                 if main_settings_file_dir:
                     actual_map_path = os.path.join(main_settings_file_dir, map_path_setting)

            logger.warning(f"Automator workflow map file not found or failed to load: {actual_map_path}. No workflows will be available.")
            self.workflows_map = {}
            return

        if not isinstance(loaded_map_content, dict):
            logger.error(f"Automator workflow map content is not a dictionary. Path: {map_path_setting}. Workflows not loaded.")
            self.workflows_map = {}
            return
            
        self.workflows_map = loaded_map_content
        logger.info(f"Automator workflows map loaded successfully. {len(self.workflows_map)} workflow groups found.")
        
        # Further validation: expand paths for each workflow
        # And potentially flatten the structure if it's grouped like in the example.
        # The example provided for the map is flat, not grouped:
        # { "workflow_name": { "path": ..., "type": ... } }
        # The example in config.py was:
        # "automator_workflows_map": { "workflow1": {"script_path": ...} }
        # The example for this task is:
        # { "open_discord": { "path": ..., "type": ... } }
        # Let's assume the map is a flat dictionary of workflow_name -> details.

        valid_workflows: Dict[str, Dict[str, Any]] = {}
        for name, config in self.workflows_map.items():
            if not isinstance(config, dict) or "path" not in config or "type" not in config:
                logger.warning(f"Invalid configuration for workflow '{name}'. Missing 'path' or 'type'. Skipping.")
                continue
            
            # Expand path if it's using ~ or environment variables
            config["path"] = os.path.expanduser(os.path.expandvars(config["path"]))
            
            if not os.path.exists(config["path"]):
                logger.warning(f"Path for workflow '{name}' does not exist: {config['path']}. This workflow may fail.")
                # Still add it, as the path might become valid later, or it's a script embedded in osascript command

            valid_workflows[name] = config
        
        self.workflows_map = valid_workflows
        if not self.workflows_map:
             logger.info("No valid automator workflows found after validation.")
        else:
            logger.info(f"{len(self.workflows_map)} valid automator workflows configured: {list(self.workflows_map.keys())}")


    def list_available_workflows(self) -> List[str]:
        return list(self.workflows_map.keys())

    def run_workflow(self, workflow_name: str, arguments: Optional[List[str]] = None) -> Tuple[bool, str]:
        if sys.platform != "darwin":
            logger.warning("Automator workflows can only be run on macOS (darwin).")
            return False, "Automator workflows are only supported on macOS."

        if workflow_name not in self.workflows_map:
            return False, f"Workflow '{workflow_name}' not found in map."

        config = self.workflows_map[workflow_name]
        path = config["path"]
        workflow_type = config.get("type", "workflow").lower() # Default to 'workflow' if type not specified
        timeout = config.get("timeout_seconds", 60) # Default timeout 60s

        # It's good practice to ensure path exists for types that require it
        if workflow_type in ["workflow", "app", "osascript_file", "shell_script"] and not os.path.exists(path):
             return False, f"Workflow file for '{workflow_name}' not found at path: {path}"


        cmd: List[str] = []
        arguments = arguments or []

        if workflow_type == "workflow":
            # Passing arguments to .workflow files:
            # Method 1: -D var=value (Automator variables)
            # This is complex for generic list of args.
            # Method 2: Input to first action (if it accepts it)
            # `automator -i "input string" /path/to/workflow.workflow`
            # For simplicity, if arguments are provided, we'll try to pass the first one as input.
            # More complex argument passing should use osascript or shell scripts.
            cmd = ["automator"]
            if arguments:
                # automator CLI's -i flag takes a single string. If multiple args, join them or take first.
                cmd.extend(["-i", " ".join(arguments)]) 
            cmd.append(path)

        elif workflow_type == "app":
            # `open /path/to/app --args arg1 arg2`
            cmd = ["open", path]
            if arguments:
                cmd.append("--args")
                cmd.extend(arguments)
        
        elif workflow_type == "osascript_file": # for .scpt or .applescript files
            cmd = ["osascript", path] + arguments
        
        elif workflow_type == "osascript_command": # for commands like 'tell app "..."'
            # The 'path' field here would contain the AppleScript command itself.
            cmd = ["osascript", "-e", path] 
            # Note: Passing arguments to -e scripts is tricky. They are not directly available via 'argv'.
            # Users should embed arguments into the osascript -e command string itself if using this type,
            # or use osascript_file for easier argument passing.
            # Example: path = f"tell application \"Reminders\" to make new reminder with properties {{name:\"{arguments[0] if arguments else ''}\"}}"
            # This means the command string itself must be constructed with arguments.
            # For a generic runner, this type is less flexible for arbitrary arguments.
            # We will assume if arguments are provided, they are meant to be appended, though this might not always work for -e.
            if arguments:
                 logger.warning("Passing arguments to 'osascript_command' type might not work as expected unless the command string is designed to accept them or they are appended for a script that can take them.")
                 cmd.extend(arguments) # This is how you pass to a script, but -e is not a script file.

        elif workflow_type == "shell_script": # for .sh files
            # Make sure it's executable or run with sh/bash
            if not os.access(path, os.X_OK):
                cmd = ["/bin/sh", path] + arguments # or bash
            else:
                cmd = [path] + arguments
        
        elif workflow_type == "osascript_shell": # A shell script run via osascript (less common, but for completeness)
            # This would be something like: osascript -e 'do shell script "/path/to/script.sh arg1 arg2"'
            # Requires arguments to be embedded in the shell script string.
            # The 'path' should be the shell script path.
            shell_command_to_run = path
            if arguments:
                shell_command_to_run += " " + " ".join([f"'{arg}'" for arg in arguments]) # Basic quoting
            cmd = ["osascript", "-e", f'do shell script "{shell_command_to_run}"']

        else:
            return False, f"Unsupported workflow type '{workflow_type}' for '{workflow_name}'."

        logger.info(f"Running workflow '{workflow_name}' with command: {' '.join(cmd)}")

        try:
            process = subprocess.run(cmd, capture_output=True, text=True, check=False, timeout=timeout)
            success = process.returncode == 0
            output_message = f"Stdout:\n{process.stdout}\nStderr:\n{process.stderr}"
            if not success:
                logger.warning(f"Workflow '{workflow_name}' failed with return code {process.returncode}.\nOutput:\n{output_message}")
            else:
                logger.info(f"Workflow '{workflow_name}' completed successfully.\nOutput:\n{output_message}")
            return success, output_message
        except subprocess.TimeoutExpired:
            logger.error(f"Workflow '{workflow_name}' timed out after {timeout} seconds.")
            return False, f"Workflow '{workflow_name}' timed out after {timeout} seconds."
        except FileNotFoundError:
            logger.error(f"Command not found for workflow '{workflow_name}'. Main command: {cmd[0]}. Please ensure it's installed and in PATH.")
            return False, f"Command for workflow '{workflow_name}' ({cmd[0]}) not found."
        except Exception as e:
            logger.error(f"Error running workflow '{workflow_name}': {e}", exc_info=True)
            return False, f"An unexpected error occurred: {e}"


if __name__ == '__main__':
    # This is a mock AppSettings for testing AutomatorRunner directly.
    # In a real scenario, AppSettings would be properly initialized by the agent.
    class MockAppSettings:
        def __init__(self, settings_data: Dict[str, Any], main_config_dir: Optional[str] = None):
            self.settings = settings_data
            self._main_settings_file_dir = main_config_dir or os.getcwd() # Used for resolving relative paths

        def get_config(self, key: str, default: Any = None) -> Any:
            return self.settings.get(key, default)

        def get_automator_workflows_map(self) -> Optional[Dict[str, Any]]:
            # This mock directly returns the map content if it's in settings,
            # or tries to load it if a path is given (more like real AppSettings)
            map_data = self.settings.get("automator_workflows_map")
            if isinstance(map_data, str): # If it's a path string
                path = map_data
                if not os.path.isabs(path):
                    path = os.path.join(self._main_settings_file_dir, path)
                if os.path.exists(path):
                    try:
                        with open(path, 'r') as f:
                            return json.load(f)
                    except json.JSONDecodeError:
                        logger.error(f"MockAppSettings: Failed to decode JSON from {path}")
                        return None
                else:
                    logger.warning(f"MockAppSettings: Map file path does not exist {path}")
                    return None
            return map_data # Assume it's already loaded map content


    logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    
    # Create dummy workflow files for testing if on macOS
    if sys.platform == "darwin":
        os.makedirs("temp_automator_workflows", exist_ok=True)
        
        # Dummy .workflow (simulated by a shell script)
        dummy_workflow_path = "temp_automator_workflows/TestEcho.workflow"
        with open(dummy_workflow_path, "w") as f:
            # A .workflow is a directory. We can't easily create a real one.
            # We will simulate it with a shell script that automator CLI might call,
            # or more realistically, we'll test types that are files e.g. .sh, .scpt
            # For 'workflow' type, the actual `automator` CLI expects a proper bundle.
            # Let's create a shell script and use 'shell_script' type for a reliable test.
            pass # Cannot create a fake .workflow this way.

        # Dummy shell script
        dummy_shell_script_path = "temp_automator_workflows/test_script.sh"
        with open(dummy_shell_script_path, "w") as f:
            f.write("#!/bin/sh\n")
            f.write('echo "Shell script executed!"\n')
            f.write('echo "Argument 1: $1"\n')
            f.write('echo "Argument 2: $2"\n')
            f.write('echo "Error output from shell" >&2\n')
        os.chmod(dummy_shell_script_path, 0o755)

        # Dummy AppleScript file
        dummy_applescript_path = "temp_automator_workflows/test_script.scpt"
        with open(dummy_applescript_path, "w") as f:
            f.write('on run argv\n')
            f.write('  log "AppleScript executed!"\n')
            f.write('  set output to "AppleScript output. Args: "\n')
            f.write('  repeat with arg in argv\n')
            f.write('    set output to output & arg & " "\n')
            f.write('  end repeat\n')
            f.write('  return output\n')
            f.write('end run\n')

        automator_map_content = {
            "echo_test_shell": {
                "path": dummy_shell_script_path,
                "type": "shell_script",
                "description": "Runs a test shell script."
            },
            "echo_test_applescript": {
                "path": dummy_applescript_path,
                "type": "osascript_file",
                "description": "Runs a test AppleScript file."
            },
            "list_desktop": { # A real command that should work on macOS
                "path": "ls -la ~/Desktop", # This is not a path, this is a command
                "type": "osascript_command", # This will be 'osascript -e path' -> osascript -e 'ls -la ~/Desktop' which is wrong
                                            # This should be: osascript -e 'do shell script "ls -la ~/Desktop"'
                "description": "Lists desktop contents via osascript do shell script."
            },
             "list_desktop_fixed": {
                "path": 'do shell script "ls -la ~/Desktop"', # The actual AppleScript command part
                "type": "osascript_command",
                "description": "Lists desktop contents via osascript do shell script."
            },
            "nonexistent_workflow": {
                "path": "temp_automator_workflows/nonexistent.workflow",
                "type": "workflow",
                "description": "A workflow that does not exist."
            }
        }
    else: # Not on macOS, create a dummy map
        automator_map_content = {
            "echo_test_shell": {
                "path": "dummy_script.sh",
                "type": "shell_script",
                "description": "Dummy shell script for non-macOS."
            }
        }

    # Create a dummy map file if you want to test loading from path
    # temp_map_file_path = "temp_automator_map.json"
    # with open(temp_map_file_path, 'w') as f:
    #    json.dump(automator_map_content, f)
    # mock_app_settings = MockAppSettings({"automator_workflows_map_path": temp_map_file_path})
    
    # For testing, pass the content directly if MockAppSettings supports it
    mock_app_settings = MockAppSettings({"automator_workflows_map": automator_map_content})
    
    runner = AutomatorRunner(mock_app_settings)

    print("Available workflows:", runner.list_available_workflows())
    assert "echo_test_shell" in runner.list_available_workflows()
    if sys.platform == "darwin":
         assert "echo_test_applescript" in runner.list_available_workflows()


    print("\n--- Running echo_test_shell ---")
    success, output = runner.run_workflow("echo_test_shell", ["hello", "world"])
    print(f"Success: {success}\nOutput:\n{output}")
    assert success == (True if sys.platform == "darwin" else False) # Only runs on darwin
    if sys.platform == "darwin":
        assert "Shell script executed!" in output
        assert "Argument 1: hello" in output
        assert "Error output from shell" in output # Stderr is captured

    if sys.platform == "darwin":
        print("\n--- Running echo_test_applescript ---")
        success, output = runner.run_workflow("echo_test_applescript", ["applescript_param1", "param2"])
        print(f"Success: {success}\nOutput:\n{output}")
        assert success
        assert "AppleScript output. Args: applescript_param1 param2" in process.stdout if success else True # stdout is in process.stdout

        print("\n--- Running list_desktop_fixed (osascript_command) ---")
        success, output = runner.run_workflow("list_desktop_fixed")
        print(f"Success: {success}\nOutput:\n{output}")
        assert success 
        # Output will contain desktop listing, too variable to assert specific content beyond no error.
        assert "Stderr:\n" in output # Expect empty stderr for this command if successful

        print("\n--- Running nonexistent_workflow ---")
        success, output = runner.run_workflow("nonexistent_workflow")
        print(f"Success: {success}\nOutput:\n{output}")
        assert not success
        assert "not found at path" in output

    print("\n--- Running workflow not in map ---")
    success, output = runner.run_workflow("fake_workflow")
    print(f"Success: {success}\nOutput:\n{output}")
    assert not success
    assert "not found in map" in output
    
    # Clean up dummy files
    if sys.platform == "darwin":
        try:
            os.remove(dummy_shell_script_path)
            os.remove(dummy_applescript_path)
            # os.remove(dummy_workflow_path) # This was never a real file
            os.rmdir("temp_automator_workflows")
        except OSError as e:
            print(f"Error cleaning up dummy files: {e}")
    # if os.path.exists(temp_map_file_path): os.remove(temp_map_file_path)

    logger.info("AutomatorRunner test finished.")
