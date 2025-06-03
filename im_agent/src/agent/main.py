import asyncio
import json
import logging
import os
import signal
import sys
import argparse # For command-line arguments
import functools # For partial application
from collections import defaultdict, deque # Should be in AgentState or MemoryManager now
from typing import Any, Dict, List, Optional, Deque, Coroutine

# --- Configuration and Logging ---
# Assuming config.py provides a global 'settings' instance or a load function
# For this refactor, let's assume AppSettings is the class and we instantiate it.
# The old 'global_settings' might need to be re-thought if main.py is the sole entry point for config loading.
from agent.config import AppSettings # Assuming AppSettings loads default path or uses env var
from agent.utils.logging_config import setup_logging

# --- Core Components ---
from agent.core.state import AgentState
from agent.core.main_graph import create_agent_graph

# --- Tooling ---
from agent.tools.llm.factory import LLMFactory
from agent.tools.mcp.factory import MCPFactory
# from agent.tools.rpa.factory import RPAFactory # RPA not directly used by graph yet, but factory can be init'd
from agent.memory.manager import MemoryManager

# --- IM Interface ---
# Adjust path if im_interface is not directly under src (it is: src/im_interface)
# This means the path from 'agent' (which is src/agent) is '../im_interface'
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))) # Add 'src' to path
from im_interface.im import get_im_adapters, IMInterface # type: ignore

# --- API and Server ---
from agent.api import app as fastapi_app # FastAPI app instance from agent.api.__init__
import uvicorn

logger = logging.getLogger(__name__)

# Define default config file path relative to the project root (im_agent directory)
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")) # Up from src/agent/
DEFAULT_CONFIG_FILE = os.path.join(PROJECT_ROOT, "config", "settings.json")

# Global variable to hold the compiled LangGraph app
# This will be accessed by the IM message handler and REST API handler
langgraph_app: Optional[Any] = None # Type hint with compiled graph type if available
active_im_adapters_dict: Dict[str, IMInterface] = {} # For sending replies from IM handler

# Event for graceful shutdown handling
shutdown_event = asyncio.Event()


async def im_message_handler(raw_im_message: Dict[str, Any]):
    """
    Callback for IM adapters. Invokes the LangGraph application with the received message.
    """
    global langgraph_app, active_im_adapters_dict # Allow access to global instances
    if not langgraph_app:
        logger.error("LangGraph app not initialized. Cannot process IM message.")
        # Potentially send error back to user if possible, though adapter might not be ready
        return

    logger.info(f"IM Handler received: {raw_im_message}")

    # Extract chat_id for thread_id in LangGraph
    chat_id = raw_im_message.get("chat_id", "default_chat_id") # Fallback if chat_id is missing

    # Initial state for the graph invocation
    initial_state: AgentState = {
        "raw_im_message": raw_im_message,
        "conversation_history": [], # Will be populated by process_im_message_node
        # Other fields will be populated by the first node (process_im_message_node)
    }

    try:
        # Configure the graph to run with a specific thread_id (e.g., chat_id)
        # This is crucial for checkpointers and maintaining separate states per conversation.
        config = {"configurable": {"thread_id": chat_id}}

        # Stream events from the graph invocation
        # final_state_events = [] # To capture all events if needed
        # async for event_part in langgraph_app.astream_events(initial_state, config=config, version="v1"):
        #     # Process events here (e.g., send to event_emitter)
        #     # logger.debug(f"Graph event: {event_part}")
        #     # final_state_events.append(event_part)
        # # The final state is typically the last 'values' in the 'end' event, or needs specific extraction.

        # For now, using ainvoke to get the final state directly for simplicity.
        # Streaming with astream_events is better for real-time updates to frontend.
        final_state = await langgraph_app.ainvoke(initial_state, config=config)

        logger.info(f"Graph execution complete for chat_id '{chat_id}'. Final state keys: {final_state.keys()}")

        response_to_user = final_state.get("final_response_to_user")
        error_to_user = final_state.get("error_message_to_user")
        platform = final_state.get("platform") # Should be populated by process_im_message_node
        # chat_id is already known

        if error_to_user: # Prioritize sending explicit error messages
            logger.error(f"Error message for user in chat_id '{chat_id}': {error_to_user}")
            if platform and chat_id and platform in active_im_adapters_dict:
                await active_im_adapters_dict[platform].send_message(chat_id, error_to_user)
            else:
                logger.error(f"Could not send error to user: Platform '{platform}' or chat_id '{chat_id}' missing, or adapter not found.")
        elif response_to_user:
            logger.info(f"Final response for chat_id '{chat_id}': {response_to_user}")
            if platform and chat_id and platform in active_im_adapters_dict:
                await active_im_adapters_dict[platform].send_message(chat_id, response_to_user)
            else:
                logger.error(f"Could not send response: Platform '{platform}' or chat_id '{chat_id}' missing, or adapter not found.")
        else:
            logger.warning(f"No final_response_to_user or error_message_to_user in final state for chat_id '{chat_id}'. State: {final_state}")

    except Exception as e:
        logger.error(f"Error during LangGraph app invocation for chat_id '{chat_id}': {e}", exc_info=True)
        # Attempt to send a generic error message back to the user if possible
        platform = raw_im_message.get("platform")
        chat_id_err = raw_im_message.get("chat_id")
        if platform and chat_id_err and platform in active_im_adapters_dict:
            try:
                await active_im_adapters_dict[platform].send_message(chat_id_err, "Sorry, a critical error occurred while processing your request.")
            except Exception as send_err:
                logger.error(f"Failed to send critical error message to user {platform}:{chat_id_err}: {send_err}")


async def main_async(config_path: str):
    """
    Main asynchronous function to initialize and run the agent application.
    """
    global langgraph_app, active_im_adapters_dict # To assign to global variables

    # 1. Load Configuration
    app_settings = AppSettings() # Instantiates with default path or env var logic
    try:
        # If AppSettings doesn't load on init, or if a specific path is given:
        if not app_settings.settings or config_path != DEFAULT_CONFIG_FILE:
             app_settings.load_config(config_path) # Load specified or ensure default is loaded
        logger.info(f"Configuration loaded from: {config_path}")
    except Exception as e:
        # Use basic logging if setup_logging hasn't run yet
        logging.basicConfig(level=logging.ERROR)
        logger.fatal(f"Failed to load configuration from {config_path}: {e}", exc_info=True)
        return # Critical failure

    # 2. Setup Logging (as early as possible after config is loaded)
    try:
        setup_logging(log_level_str=app_settings.log_level)
        logger.info(f"Logging configured with level: {app_settings.log_level}")
    except Exception as e:
        logger.error(f"Error setting up logging: {e}", exc_info=True)
        # Continue with basic logging if setup fails

    # 3. Initialize Core Components
    try:
        logger.info("Initializing LLM client...")
        llm_config = app_settings.get_llm_config()
        llm_provider = app_settings.get_config("llm_provider", "DummyLLM")
        llm_client = await LLMFactory.get_llm_client(llm_provider, llm_config)
        if not llm_client:
            raise RuntimeError(f"Failed to initialize LLM client for provider {llm_provider}.")
        logger.info(f"LLM Client '{type(llm_client).__name__}' initialized.")

        logger.info("Initializing MemoryManager...")
        memory_config = app_settings.get_config("memory_config", {}) # Get memory specific config
        # Ensure resolved path for LTM is passed if relative
        if 'long_term_storage_path' in memory_config and not os.path.isabs(memory_config['long_term_storage_path']):
            memory_config['long_term_storage_path'] = os.path.join(PROJECT_ROOT, memory_config['long_term_storage_path'])

        memory_manager = MemoryManager(config=memory_config)
        if not await memory_manager.initialize():
             raise RuntimeError("Failed to initialize MemoryManager.")
        logger.info("MemoryManager initialized.")

        # Initialize MCP Client (example: taking the first configured general MCP connection)
        # In a multi-MCP setup, the graph might need access to a factory or multiple clients.
        # For now, assume one primary MCP handler is passed to the graph if needed by specific nodes.
        # The current graph nodes don't directly take mcp_client at construction.
        # Tool execution nodes would fetch it from a shared context or a factory.
        # For now, we just initialize it to ensure it's ready if any part of the system needs it.
        mcp_connections = app_settings.get_config("mcp_connections", [])
        if mcp_connections:
            # Example: Initialize the first "general" type MCP connection
            general_mcp_config = next((c for c in mcp_connections if c.get("type") == "general"), None)
            if general_mcp_config:
                logger.info(f"Initializing general MCP client for connection: {general_mcp_config.get('name')}")
                # Ensure paths in client_config are resolved relative to project root if not absolute
                client_cfg = general_mcp_config.get("client_config", {})
                for path_key in ["mcp_servers_config_path", "whitelist_file_path"]:
                    if path_key in client_cfg and not os.path.isabs(client_cfg[path_key]):
                        client_cfg[path_key] = os.path.join(PROJECT_ROOT, client_cfg[path_key])

                mcp_client = await MCPFactory.get_mcp_client(general_mcp_config)
                if mcp_client:
                    logger.info(f"MCP Client '{type(mcp_client).__name__}' for '{general_mcp_config.get('name')}' initialized.")
                    # Make it available to FastAPI if needed (e.g. for a list services endpoint)
                    fastapi_app.state.mcp_client = mcp_client
                else:
                    logger.warning(f"Failed to initialize MCP client for '{general_mcp_config.get('name')}'.")

        # Initialize RPA Factory (RPA clients are typically platform-specific and might be lazy-loaded by nodes)
        # rpa_factory = RPAFactory() # If RPAFactory needs init, do it here.
        # logger.info("RPAFactory available.")
        # fastapi_app.state.rpa_factory = rpa_factory # Make available to API if needed

    except RuntimeError as e:
        logger.fatal(f"Failed to initialize a core component: {e}", exc_info=True)
        return # Critical failure

    # 4. Create and Compile LangGraph App
    logger.info("Creating and compiling LangGraph application...")
    try:
        agent_graph_definition = create_agent_graph(llm_client=llm_client, memory_manager=memory_manager)
        # TODO: Add checkpointer here for persistence when ready
        # from langgraph.checkpoint.sqlite import SqliteSaver
        # memory_for_graph = SqliteSaver.from_conn_string(":memory:") # In-memory example
        # langgraph_app = agent_graph_definition.compile(checkpointer=memory_for_graph)
        langgraph_app = agent_graph_definition.compile()
        logger.info("LangGraph application compiled successfully.")
    except Exception as e:
        logger.fatal(f"Failed to create or compile LangGraph application: {e}", exc_info=True)
        return # Critical failure

    # Make langgraph_app and memory_manager available to FastAPI app state for REST endpoint
    fastapi_app.state.langgraph_app = langgraph_app
    fastapi_app.state.memory_manager = memory_manager
    fastapi_app.state.app_settings = app_settings # For general config access in API if needed

    # 5. Initialize and Start IM Adapters (if configured)
    im_adapter_tasks = []
    im_settings = app_settings.get_im_settings()
    if im_settings: # Check if im_settings itself is present and not empty
        logger.info("Initializing IM adapters...")
        # The get_im_adapters function in im_interface.im.__init__ now expects AppSettings directly
        # and then it accesses im_settings internally.
        # We need to pass the app_settings object.
        im_adapters_list = await get_im_adapters(app_settings, im_message_handler)

        active_im_adapters_dict.update({adapter.platform_name: adapter for adapter in im_adapters_list})

        for platform, adapter in active_im_adapters_dict.items():
            logger.info(f"Attempting to connect and start listening for IM platform: {platform}")
            # Using a wrapper to handle connection before listening
            async def connect_and_listen_wrapper(adapter_instance: IMInterface):
                try:
                    if await adapter_instance.connect():
                        logger.info(f"IM Adapter {adapter_instance.platform_name} connected.")
                        await adapter_instance.start_listening()
                    else:
                        logger.error(f"IM Adapter {adapter_instance.platform_name} failed to connect.")
                except Exception as e_adapter:
                    logger.error(f"Error with IM Adapter {adapter_instance.platform_name}: {e_adapter}", exc_info=True)
                finally:
                    logger.info(f"IM Adapter {adapter_instance.platform_name} listening stopped or failed to start.")

            im_adapter_tasks.append(asyncio.create_task(connect_and_listen_wrapper(adapter)))
        if im_adapter_tasks:
            logger.info(f"{len(im_adapter_tasks)} IM adapter tasks created.")
        else:
            logger.info("No IM adapters enabled or configured to run.")
    else:
        logger.info("No IM settings found in configuration. IM adapters will not be started.")

    # 6. Setup and Start FastAPI/Uvicorn Server
    server_host = app_settings.get_config("server_host", "0.0.0.0")
    server_port = app_settings.get_config("server_port", 8000)
    debug_mode = app_settings.get_config("debug_mode", False)

    uvicorn_config = uvicorn.Config(
        app=fastapi_app, # Use the imported app
        host=server_host,
        port=server_port,
        log_level=app_settings.log_level.lower(),
        reload=debug_mode
    )
    server = uvicorn.Server(uvicorn_config)

    logger.info(f"Starting Uvicorn server on {server_host}:{server_port}")
    api_server_task = asyncio.create_task(server.serve())
    im_adapter_tasks.append(api_server_task) # Add server task to list for graceful shutdown

    # 7. Run until shutdown signal
    await shutdown_event.wait() # Wait for signal handler to set this event

    # 8. Graceful Shutdown
    logger.info("Initiating graceful shutdown...")
    if hasattr(server, 'should_exit') and not server.should_exit: # Check if uvicorn server has this attribute
        server.should_exit = True # Tell Uvicorn to stop accepting new connections
        # await server.shutdown() # This might be needed for some uvicorn versions or if server.serve() is not awaited directly

    # Gracefully stop IM adapters
    for platform, adapter in active_im_adapters_dict.items():
        if hasattr(adapter, 'is_connected') and adapter.is_connected:
            logger.info(f"Disconnecting IM adapter: {platform}")
            await adapter.disconnect()

    # Cancel all running tasks (IM adapters, API server)
    for task in im_adapter_tasks:
        if not task.done():
            task.cancel()

    # Wait for tasks to complete cancellation
    await asyncio.gather(*im_adapter_tasks, return_exceptions=True)
    logger.info("All tasks (IM adapters, API server) have been processed for shutdown.")


def handle_shutdown_signal(sig, frame):
    logger.info(f"Received signal {sig}. Setting shutdown event.")
    # This function should only call async-safe functions if called from an asyncio loop's thread.
    # Setting an asyncio.Event is generally safe.
    asyncio.create_task(set_shutdown_event())

async def set_shutdown_event():
    shutdown_event.set()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="IM-Agent: macOS Desktop Automation Smart Agent")
    parser.add_argument(
        "--config_path",
        type=str,
        default=DEFAULT_CONFIG_FILE,
        help=f"Path to the agent's configuration file (default: {DEFAULT_CONFIG_FILE})",
    )
    args = parser.parse_args()

    # Setup signal handlers for graceful shutdown
    # For Windows, SIGINT (Ctrl+C) is usually handled by KeyboardInterrupt in asyncio.run
    if sys.platform != "win32":
        signal.signal(signal.SIGINT, handle_shutdown_signal)
        signal.signal(signal.SIGTERM, handle_shutdown_signal)

    try:
        asyncio.run(main_async(args.config_path))
    except KeyboardInterrupt: # Catches Ctrl+C, especially on Windows
        logger.info("KeyboardInterrupt received. Initiating shutdown...")
        # If the loop is already stopping/stopped, this might not do much more,
        # but if it's caught before shutdown_event is set, this helps.
        if not shutdown_event.is_set():
             shutdown_event.set() # Trigger graceful shutdown if not already triggered
             # Re-running main_async or parts of it here is problematic.
             # The shutdown_event should be sufficient for the running main_async to handle cleanup.
    except Exception as e:
        logger.fatal(f"Unhandled exception in __main__: {e}", exc_info=True)
    finally:
        logger.info("IM-Agent application has shut down.")
