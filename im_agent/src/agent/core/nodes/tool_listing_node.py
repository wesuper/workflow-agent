import asyncio # For potential async file I/O later
import json
import logging
import os # For path operations
from typing import Dict, Any, List, Optional

# Corrected relative imports
from ..state import AgentState
from ...tools.mcp.base import AbstractMCPClient
# RPAFactory is not directly used if rpa_scripts_config_path is passed directly.
# If RPA clients were needed to list their own scripts (less common for file-based defs), then factory would be needed.
# from ...tools.rpa.factory import RPAFactory
from ...api.event_emitter import event_emitter

logger = logging.getLogger(__name__)

async def list_mcp_services_node(state: AgentState, mcp_client: AbstractMCPClient) -> Dict[str, Any]:
    """
    Retrieves the list of available MCP services from the MCP client
    and updates the agent state.
    """
    chat_id = state.get("chat_id", "unknown_chat")
    logger.info(f"Listing MCP services for chat_id '{chat_id}'...")

    try:
        services: List[Dict[str, Any]] = await mcp_client.list_services()
        logger.info(f"Retrieved {len(services)} MCP services for chat_id '{chat_id}'.")
        await event_emitter.emit(
            event_type="mcp_services_listed",
            data={"chat_id": chat_id, "service_count": len(services), "services_sample": services[:3]}, # Emit sample
            chat_id=chat_id
        )
        # Clear previous LLM response and parsed action as this node fulfills the [REQUEST:...]
        return {
            "available_mcp_services": services,
            "llm_response_text": None,
            "parsed_action": None,
            "tool_error": None # Clear any previous tool error after successful listing
        }
    except Exception as e:
        logger.error(f"Error listing MCP services for chat_id '{chat_id}': {e}", exc_info=True)
        await event_emitter.emit(
            event_type="mcp_services_listed_error",
            data={"chat_id": chat_id, "error": str(e)},
            chat_id=chat_id
        )
        return {
            "available_mcp_services": [], # Return empty list on error
            "llm_response_text": None,
            "parsed_action": None,
            "tool_error": f"Failed to list MCP services: {str(e)}"
        }


async def list_rpa_scripts_node(state: AgentState, rpa_scripts_config_path: Optional[str]) -> Dict[str, Any]:
    """
    Lists available RPA scripts by loading them from a specified configuration file.
    The configuration file is expected to be a JSON dictionary mapping platforms
    (e.g., "macos", "android") to lists of script definitions.
    """
    chat_id = state.get("chat_id", "unknown_chat")
    requested_platform = state.get("parsed_action", {}).get("rpa_platform") # From parser, e.g. "macos"

    logger.info(f"Listing RPA scripts for chat_id '{chat_id}'. Config path: '{rpa_scripts_config_path}'. Requested platform: {requested_platform}")

    available_scripts_by_platform: Dict[str, List[Dict[str, Any]]] = {"macos": [], "android": []}
    error_msg: Optional[str] = None

    if rpa_scripts_config_path:
        # Resolve path if relative (e.g., relative to project root or a known config root)
        # For now, assume it's either absolute or resolvable from CWD if not.
        # A robust solution would involve AppSettings providing a base path.
        actual_config_path = rpa_scripts_config_path
        if not os.path.isabs(actual_config_path):
            # This path resolution might need to be more sophisticated, e.g. using PROJECT_ROOT from main.py context
            actual_config_path = os.path.abspath(actual_config_path)
            logger.debug(f"Resolved relative RPA scripts config path to: {actual_config_path}")

        try:
            if not await asyncio.to_thread(os.path.exists, actual_config_path):
                raise FileNotFoundError(f"RPA scripts config file not found at {actual_config_path}")

            # Use asyncio.to_thread for synchronous file I/O
            def read_json_sync(path):
                with open(path, 'r') as f:
                    return json.load(f)

            config_data = await asyncio.to_thread(read_json_sync, actual_config_path)

            if isinstance(config_data, dict):
                if requested_platform: # User asked for scripts for a specific platform
                    if requested_platform in config_data:
                        available_scripts_by_platform[requested_platform] = config_data.get(requested_platform, [])
                    else:
                        logger.warning(f"Requested RPA platform '{requested_platform}' not found in config file '{actual_config_path}'.")
                        # error_msg = f"No RPA scripts found for platform '{requested_platform}'." # Or just return empty for that platform
                else: # No specific platform requested, load all
                    available_scripts_by_platform["macos"] = config_data.get("macos", [])
                    available_scripts_by_platform["android"] = config_data.get("android", [])
            else:
                error_msg = "RPA scripts config is not in the expected format (dict with 'macos'/'android' keys)."
                logger.error(error_msg + f" Path: {actual_config_path}")

        except FileNotFoundError:
            error_msg = f"RPA scripts config file not found: {actual_config_path}"
            logger.error(error_msg)
        except json.JSONDecodeError as e:
            error_msg = f"Error decoding RPA scripts config file: {actual_config_path} - {str(e)}"
            logger.error(error_msg, exc_info=True)
        except Exception as e:
            error_msg = f"Unexpected error loading RPA scripts from {actual_config_path}: {str(e)}"
            logger.error(error_msg, exc_info=True)
    else:
        error_msg = "RPA scripts configuration path not provided to list_rpa_scripts_node."
        logger.warning(error_msg)

    await event_emitter.emit(
        event_type="rpa_scripts_listed" if not error_msg else "rpa_scripts_listed_error",
        data={
            "chat_id": chat_id,
            "requested_platform": requested_platform,
            "macos_count": len(available_scripts_by_platform.get("macos", [])),
            "android_count": len(available_scripts_by_platform.get("android", [])),
            "error": error_msg if error_msg else None
        },
        chat_id=chat_id
    )

    # Clear previous LLM response and parsed action as this node fulfills the [REQUEST:...]
    return {
        "available_rpa_scripts": available_scripts_by_platform,
        "llm_response_text": None,
        "parsed_action": None,
        "tool_error": error_msg # Set tool_error if loading/parsing failed
    }
