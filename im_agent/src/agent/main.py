import asyncio
import json
import logging
import os
import signal
import sys
from collections import defaultdict, deque
from typing import Any, Dict, List, Optional, Deque, Coroutine

# Project imports - assuming they are discoverable in PYTHONPATH
# Adjust paths if necessary, e.g., if src is not directly in PYTHONPATH
try:
    from config import AppSettings, settings as global_settings # Use global_settings for AppSettings instance
    from utils.logging_config import setup_logging
    from llm import get_llm_adapter, LLMInterface
    from mcp import get_mcp_handler, MCPInterface
    from automator import get_automator_runner, AutomatorRunner
    from im import get_im_adapters, IMInterface
except ImportError:
    # Fallback for cases where 'src' is the current working directory or not in python path
    # This often happens in IDEs or when running scripts directly from within 'src'
    # This assumes that main.py is in agent/ and other modules are relative to agent/
    sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
    from agent.config import AppSettings, settings as global_settings
    from agent.utils.logging_config import setup_logging
    from agent.llm import get_llm_adapter, LLMInterface
    from agent.mcp import get_mcp_handler, MCPInterface
    from agent.automator import get_automator_runner, AutomatorRunner
    from agent.im import get_im_adapters, IMInterface


logger = logging.getLogger(__name__)

# Define default config file path relative to the project root (im_agent directory)
# Assuming main.py is in im_agent/src/agent/
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
DEFAULT_CONFIG_FILE = os.path.join(PROJECT_ROOT, "config", "settings.json")


class Agent:
    def __init__(self, config_file_path: str = DEFAULT_CONFIG_FILE):
        self.config_file_path = config_file_path
        self.app_settings: AppSettings = global_settings # Use the globally configured AppSettings instance
        
        # Components to be initialized in setup()
        self.llm_adapter: Optional[LLMInterface] = None
        self.mcp_handler: Optional[MCPInterface] = None
        self.automator_runner: Optional[AutomatorRunner] = None
        self.active_im_adapters: Dict[str, IMInterface] = {}
        
        # Conversation history store: maps chat_id (platform_chatid) to a deque of messages
        self.conversation_histories: defaultdict[str, Deque[Dict[str, str]]] = \
            defaultdict(lambda: deque(maxlen=self.app_settings.get_config("conversation_history_max_length", 10)))

        self._running_tasks: List[asyncio.Task] = []
        self._stop_event = asyncio.Event()


    async def setup(self):
        """Load configurations and initialize components."""
        try:
            # Load application settings using the global instance
            # The global `settings` object from `config.py` is already an AppSettings instance.
            # If it's not loaded, we need to load it.
            # Check if settings are already loaded (e.g. by its own __init__ or a prior call)
            # This logic depends on how AppSettings is designed. If it loads on init, fine.
            # If load_config needs to be called explicitly:
            if not self.app_settings.settings: # A simple check if settings are populated
                 logger.info(f"AppSettings appears empty, attempting to load from: {self.config_file_path}")
                 self.app_settings.load_config(self.config_file_path)
            
            # Re-initialize conversation_histories maxlen in case it changed via config
            history_maxlen = self.app_settings.get_config("conversation_history_max_length", 10)
            self.conversation_histories = defaultdict(lambda: deque(maxlen=history_maxlen))

            # Configure logging (must be done after settings are loaded)
            setup_logging(log_level_str=self.app_settings.log_level) # Pass string from settings
            logger.info(f"Logging configured with level: {self.app_settings.log_level}")

            logger.info("Initializing LLM adapter...")
            self.llm_adapter = get_llm_adapter(self.app_settings)
            logger.info(f"LLM adapter initialized: {type(self.llm_adapter).__name__}")

            logger.info("Initializing MCP handler...")
            self.mcp_handler = get_mcp_handler(self.app_settings)
            logger.info(f"MCP handler initialized: {type(self.mcp_handler).__name__}")

            if sys.platform == "darwin":
                logger.info("Initializing Automator runner (macOS detected)...")
                self.automator_runner = get_automator_runner(self.app_settings)
                if self.automator_runner:
                    logger.info(f"Automator runner initialized: {type(self.automator_runner).__name__}")
                else:
                    logger.warning("Automator runner could not be initialized on macOS.")
            else:
                logger.info("Automator runner is disabled (not on macOS).")

            logger.info("Agent setup complete.")

        except Exception as e:
            logger.error(f"Error during agent setup: {e}", exc_info=True)
            # Depending on the severity, might want to raise this to stop the agent
            raise RuntimeError(f"Agent setup failed: {e}")


    async def _on_im_message(self, message: Dict[str, Any]):
        """Core callback passed to IM adapters to handle incoming messages."""
        logger.info(f"Received message: {message}")
        
        # Ensure essential message fields are present
        platform = message.get("platform")
        chat_id = message.get("chat_id")
        user_id = message.get("user_id")
        text = message.get("text")

        if not all([platform, chat_id, user_id, text]):
            logger.warning(f"Message missing essential fields (platform, chat_id, user_id, text): {message}")
            return

        conversation_key = f"{platform}_{chat_id}"
        history_for_chat = self.conversation_histories[conversation_key]
        
        # Add current user message to history
        history_for_chat.append({"role": "user", "content": text})
        logger.debug(f"Updated history for {conversation_key}: {list(history_for_chat)}")

        response_text = "Sorry, I encountered an error." # Default error response

        try:
            if not self.llm_adapter:
                logger.error("LLM Adapter not initialized. Cannot process message.")
                response_text = "Error: LLM Adapter not available."
            else:
                # LLM Processing
                llm_response_str = await self.llm_adapter.get_response(
                    prompt=text,
                    conversation_history=list(history_for_chat) # Pass a copy
                )
                logger.info(f"LLM response for {conversation_key}: {llm_response_str}")

                # Action Dispatching
                # Example prefixes:
                # [ACTION:MCP:<service_name>:<json_parameters_string>]
                # [ACTION:AUTOMATOR:<workflow_name>:<json_arguments_string>]
                # [ACTION:ADD_MCP:<json_config_string>]
                
                action_handled = False
                if llm_response_str.startswith("[ACTION:MCP:"):
                    action_handled = True
                    response_text = await self._handle_mcp_action(llm_response_str, message)
                elif llm_response_str.startswith("[ACTION:AUTOMATOR:") and self.automator_runner:
                    action_handled = True
                    response_text = await self._handle_automator_action(llm_response_str, message)
                elif llm_response_str.startswith("[ACTION:ADD_MCP:"):
                    action_handled = True
                    response_text = await self._handle_add_mcp_action(llm_response_str, message)
                
                if not action_handled:
                    response_text = llm_response_str # Default reply is the LLM's text

        except Exception as e:
            logger.error(f"Error processing message for {conversation_key}: {e}", exc_info=True)
            response_text = f"An error occurred while processing your request: {e}" # More specific error to user

        # Send Response via IM
        im_adapter = self.active_im_adapters.get(platform)
        if im_adapter:
            try:
                success = await im_adapter.send_message(recipient_id=chat_id, message_content=response_text)
                if success:
                    logger.info(f"Sent reply to {conversation_key} on {platform}: {response_text}")
                    # Add agent's reply to history
                    history_for_chat.append({"role": "assistant", "content": response_text})
                else:
                    logger.error(f"Failed to send reply to {conversation_key} on {platform}.")
            except Exception as e:
                logger.error(f"Error sending IM reply to {conversation_key} on {platform}: {e}", exc_info=True)
        else:
            logger.error(f"No active IM adapter found for platform '{platform}' to send reply.")


    async def _handle_mcp_action(self, llm_response: str, original_message: Dict[str, Any]) -> str:
        logger.info(f"Handling MCP action: {llm_response}")
        if not self.mcp_handler:
            return "Error: MCP Handler is not available."
        try:
            # Format: [ACTION:MCP:<service_name>:<json_parameters_string>]
            parts = llm_response.strip("[]").split(":", 3)
            if len(parts) < 4:
                raise ValueError("Invalid MCP action format.")
            
            _action_type, _mcp_literal, service_name, params_json = parts
            params = json.loads(params_json)
            
            logger.info(f"Invoking MCP service: {service_name} with params: {params}")
            mcp_result = await asyncio.to_thread(self.mcp_handler.invoke_service, service_name, params) # Run sync mcp_handler in thread

            # For now, send raw result; could be summarized by LLM in future
            return f"MCP service '{service_name}' executed. Result: {json.dumps(mcp_result)}"
        except json.JSONDecodeError:
            logger.error("Invalid JSON in MCP action parameters.")
            return "Error: Invalid JSON parameters for MCP action."
        except ValueError as ve:
            logger.error(f"MCP Action format error: {ve}")
            return f"Error: MCP action format error: {ve}"
        except Exception as e:
            logger.error(f"Error during MCP action: {e}", exc_info=True)
            return f"Error executing MCP action: {e}"

    async def _handle_automator_action(self, llm_response: str, original_message: Dict[str, Any]) -> str:
        logger.info(f"Handling Automator action: {llm_response}")
        if not self.automator_runner: # Should also check sys.platform but runner is None if not darwin
            return "Error: Automator Runner is not available on this platform."
        try:
            # Format: [ACTION:AUTOMATOR:<workflow_name>:<json_arguments_string>]
            parts = llm_response.strip("[]").split(":", 3)
            if len(parts) < 4:
                raise ValueError("Invalid Automator action format.")

            _action_type, _automator_literal, workflow_name, args_json = parts
            args = json.loads(args_json) # Expecting a list of strings
            if not isinstance(args, list):
                raise ValueError("Automator arguments must be a JSON list of strings.")

            logger.info(f"Running Automator workflow: {workflow_name} with arguments: {args}")
            # AutomatorRunner.run_workflow is synchronous, run in thread
            success, output = await asyncio.to_thread(self.automator_runner.run_workflow, workflow_name, args)
            
            status = "succeeded" if success else "failed"
            return f"Automator workflow '{workflow_name}' {status}. Output:\n{output}"
        except json.JSONDecodeError:
            logger.error("Invalid JSON in Automator action arguments.")
            return "Error: Invalid JSON arguments for Automator action."
        except ValueError as ve:
            logger.error(f"Automator Action format error: {ve}")
            return f"Error: Automator action format error: {ve}"
        except Exception as e:
            logger.error(f"Error during Automator action: {e}", exc_info=True)
            return f"Error executing Automator action: {e}"

    async def _handle_add_mcp_action(self, llm_response: str, original_message: Dict[str, Any]) -> str:
        logger.info(f"Handling Add MCP action: {llm_response}")
        if not self.mcp_handler:
            return "Error: MCP Handler is not available."
        try:
            # Format: [ACTION:ADD_MCP:<json_config_string>]
            parts = llm_response.strip("[]").split(":", 2)
            if len(parts) < 3:
                raise ValueError("Invalid Add MCP action format.")

            _action_type, _add_mcp_literal, mcp_config_json = parts
            mcp_config = json.loads(mcp_config_json)
            user_id = original_message.get("user_id", "unknown_user") # Get user_id for whitelist check

            logger.info(f"Adding MCP service by user '{user_id}': {mcp_config}")
            # mcp_handler.add_service is synchronous, run in thread
            success = await asyncio.to_thread(self.mcp_handler.add_service, mcp_config, user_id)
            
            if success:
                return f"MCP service '{mcp_config.get('name', 'Unknown Service')}' added successfully."
            else:
                return f"Failed to add MCP service '{mcp_config.get('name', 'Unknown Service')}'. User '{user_id}' might not be whitelisted or config is invalid."
        except json.JSONDecodeError:
            logger.error("Invalid JSON in Add MCP action configuration.")
            return "Error: Invalid JSON configuration for Add MCP action."
        except ValueError as ve:
            logger.error(f"Add MCP Action format error: {ve}")
            return f"Error: Add MCP action format error: {ve}"
        except Exception as e:
            logger.error(f"Error during Add MCP action: {e}", exc_info=True)
            return f"Error adding MCP service: {e}"


    async def run(self):
        """Main orchestration method to connect and start IM adapters."""
        if not self.app_settings.settings: # Check if setup was successful / settings loaded
            logger.error("Agent setup incomplete or failed (AppSettings not loaded). Cannot run.")
            return

        logger.info("Starting IM adapters...")
        try:
            im_adapters_list = await get_im_adapters(self.app_settings, self._on_im_message)
            if not im_adapters_list:
                logger.warning("No IM adapters were loaded. The agent will not connect to any IM platform.")
                # Optionally, exit or wait indefinitely if no adapters. For now, just log.
                # self._stop_event.set() # If we want it to stop immediately
                # return
            
            self.active_im_adapters = {adapter.platform_name: adapter for adapter in im_adapters_list}
            logger.info(f"Loaded {len(self.active_im_adapters)} IM adapters: {list(self.active_im_adapters.keys())}")

            connect_coroutines: List[Coroutine[Any, Any, bool]] = []
            listen_coroutines: List[Coroutine[Any, Any, None]] = []

            for platform, adapter in self.active_im_adapters.items():
                logger.info(f"Preparing to connect adapter: {platform}")
                # Schedule connect and then listen
                # connect_coroutines.append(adapter.connect()) # This was original thought, but listen depends on connect
                
                # Instead, chain them or manage dependencies better.
                # For now, let's make a task that connects then listens.
                async def connect_and_listen(adapter_instance: IMInterface):
                    try:
                        if await adapter_instance.connect():
                            logger.info(f"Adapter {adapter_instance.platform_name} connected. Starting to listen.")
                            await adapter_instance.start_listening()
                        else:
                            logger.error(f"Adapter {adapter_instance.platform_name} failed to connect. Will not listen.")
                    except asyncio.CancelledError:
                        logger.info(f"connect_and_listen task for {adapter_instance.platform_name} cancelled.")
                    except Exception as e_cl:
                        logger.error(f"Error in connect_and_listen for {adapter_instance.platform_name}: {e_cl}", exc_info=True)
                    finally:
                        logger.info(f"connect_and_listen for {adapter_instance.platform_name} finished or was stopped.")
                        # Ensure disconnect is called if this task ends unexpectedly
                        if adapter_instance.is_connected: # is_connected should be a property of IMInterface
                             logger.info(f"Adapter {adapter_instance.platform_name} seems to have stopped listening unexpectedly. Disconnecting.")
                             await adapter_instance.disconnect()


                self._running_tasks.append(asyncio.create_task(connect_and_listen(adapter)))

            if not self._running_tasks:
                logger.info("No IM adapter tasks started. Agent might be idle or misconfigured.")
                # self._stop_event.set() # Stop if nothing to run
                # return

            logger.info(f"All ({len(self._running_tasks)}) IM adapter tasks created. Waiting for them to complete or for stop signal.")
            # Keep the main run method alive until stop_event is set
            await self._stop_event.wait()
            logger.info("Stop event received. Proceeding to shutdown.")

        except Exception as e:
            logger.error(f"Error during agent run loop: {e}", exc_info=True)
        finally:
            logger.info("Agent run loop finished. Initiating shutdown of adapters...")
            await self.shutdown_adapters()


    async def shutdown_adapters(self):
        """Gracefully disconnect all active IM adapters."""
        logger.info(f"Shutting down {len(self.active_im_adapters)} IM adapters...")
        disconnect_tasks = []
        for platform, adapter in self.active_im_adapters.items():
            # Check if adapter has 'is_connected' attribute and if it's true
            is_connected_attr = getattr(adapter, 'is_connected', False)
            # If is_connected is a callable method (property), call it
            is_connected_val = is_connected_attr() if callable(is_connected_attr) else is_connected_attr

            if is_connected_val: # Check if adapter thinks it's connected
                logger.info(f"Disconnecting adapter: {platform}")
                disconnect_tasks.append(adapter.disconnect())
            else:
                 logger.info(f"Adapter {platform} already disconnected or was never connected.")
        
        if disconnect_tasks:
            results = await asyncio.gather(*disconnect_tasks, return_exceptions=True)
            for i, result in enumerate(results):
                if isinstance(result, Exception):
                    logger.error(f"Error disconnecting adapter {disconnect_tasks[i]}: {result}") # This won't give platform name easily
            logger.info("All active IM adapters have been requested to disconnect.")
        else:
            logger.info("No IM adapters needed explicit disconnection.")
            
        # Cancel any remaining top-level tasks created in run()
        logger.info(f"Cancelling {len(self._running_tasks)} remaining listen tasks...")
        for task in self._running_tasks:
            if not task.done():
                task.cancel()
        
        if self._running_tasks:
            await asyncio.gather(*self._running_tasks, return_exceptions=True) # Wait for tasks to finish cancelling
        logger.info("All listen tasks cancelled and awaited.")


    def _handle_signal(self, signum, frame):
        logger.info(f"Received signal {signal.Signals(signum).name}. Initiating graceful shutdown...")
        # Set the event to stop the main loop and any other loops waiting on it
        self._stop_event.set()
        # In a more complex scenario, you might have multiple events or stages of shutdown.
        # For IM adapters, their start_listening loops should ideally also check self._stop_event
        # or be cancellable tasks. The current DummyIMAdapter's listen loop checks self.is_connected,
        # which disconnect() sets to False, and it's also a cancellable task.

# Global agent instance (optional, can be managed within main_async)
_agent_instance: Optional[Agent] = None

async def main_async():
    global _agent_instance
    # Initialize AppSettings globally first or pass path to Agent for it to init
    # If AppSettings loads on its own init:
    # global_settings = AppSettings(config_file_path=DEFAULT_CONFIG_FILE) # This assumes AppSettings can take path
    # For now, we use the imported global_settings which should be an instance.
    # If it's not loaded, Agent's setup will load it.
    
    _agent_instance = Agent(config_file_path=DEFAULT_CONFIG_FILE)
    
    # Setup signal handlers for graceful shutdown
    if sys.platform != "win32": # Windows has different signal handling
        signal.signal(signal.SIGINT, _agent_instance._handle_signal)
        signal.signal(signal.SIGTERM, _agent_instance._handle_signal)
    else: # Handle Ctrl+C on Windows via a different mechanism if needed, e.g. asyncio.create_server's loop handling
        try:
            # This is a common way to allow Ctrl+C to work with asyncio on Windows
            async def wakeup():
                while not _agent_instance._stop_event.is_set(): # check agent's stop event
                    await asyncio.sleep(0.1)
            asyncio.create_task(wakeup())
        except Exception as e:
            loggerinfo(f"Could not set up Windows Ctrl+C handler: {e}")


    try:
        await _agent_instance.setup()
        await _agent_instance.run()
    except RuntimeError as e: # Catch setup errors specifically if they are critical
        logger.fatal(f"Agent failed to start due to setup error: {e}", exc_info=True)
    except asyncio.CancelledError:
        logger.info("Main task cancelled, shutting down.")
    except Exception as e:
        logger.error(f"Unhandled exception in main_async: {e}", exc_info=True)
    finally:
        logger.info("Main async function finished. Ensuring final cleanup.")
        if _agent_instance and _agent_instance._stop_event.is_set(): # If shutdown was triggered
             await _agent_instance.shutdown_adapters() # Ensure adapters are shut down if not already
        elif _agent_instance: # If loop exited without stop_event (e.g. all tasks finished naturally)
             logger.info("Main loop exited without explicit stop signal. Requesting adapter shutdown.")
             await _agent_instance.shutdown_adapters()


if __name__ == "__main__":
    # Ensure the asyncio event loop is appropriate for the OS
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    
    try:
        asyncio.run(main_async())
    except KeyboardInterrupt: # This might catch Ctrl+C if signal handlers didn't fully manage it
        logger.info("KeyboardInterrupt caught in __main__. Agent shutting down.")
        # If _agent_instance exists and has shutdown logic, try to run it.
        # This is tricky because the loop is already stopping.
        # The signal handler and _stop_event are preferred.
        if _agent_instance and not _agent_instance._stop_event.is_set():
            logger.info("Setting stop event from __main__ KeyboardInterrupt.")
            _agent_instance._stop_event.set()
            # Try to run shutdown if loop isn't running anymore
            # This is best-effort at this point.
            # asyncio.run(agent_instance.shutdown_adapters()) # Careful: new loop for shutdown
    finally:
        logger.info("IM-Agent application terminated.")
