import logging
from typing import Dict, Any, Optional

# Corrected relative imports
from ..state import AgentState
from ...tools.mcp.base import AbstractMCPClient
from ...tools.rpa.base import AbstractRPAClient # For type hinting
from ...tools.rpa.factory import RPAFactory # For instantiating RPA clients
from ...api.event_emitter import event_emitter
# AppSettings might be needed if rpa_configs are fetched directly here,
# but it's better if rpa_configs is passed in.
# from ....config import AppSettings

logger = logging.getLogger(__name__)

async def execute_mcp_tool_node(state: AgentState, mcp_client: Optional[AbstractMCPClient]) -> Dict[str, Any]:
    """Executes an MCP tool call based on parsed_action."""
    chat_id = state.get("chat_id", "unknown_chat")
    parsed_action = state.get("parsed_action")

    if not mcp_client:
        logger.error(f"MCP client not available for execute_mcp_tool_node, chat_id {chat_id}")
        return {"tool_error": "MCP client is not configured or available.", "parsed_action": None}

    if not parsed_action or parsed_action.get("type") != "MCP":
        logger.warning(f"execute_mcp_tool_node called with invalid or missing MCP action in state for chat_id {chat_id}")
        return {"tool_error": "execute_mcp_tool_node called without a valid MCP action.", "parsed_action": None}

    service_name = parsed_action.get("name")
    params = parsed_action.get("params", {})
    original_llm_output = parsed_action.get("original_llm_output", "")

    if not service_name:
        logger.error(f"MCP action missing 'name' (service_name) for chat_id {chat_id}. Action: {parsed_action}")
        return {"tool_error": "MCP action is missing the service name.", "parsed_action": None}

    logger.info(f"Executing MCP tool: '{service_name}' with params: {params} for chat_id '{chat_id}'")
    await event_emitter.emit(
        event_type="tool_call_start",
        data={"chat_id": chat_id, "tool_type": "MCP", "tool_name": service_name, "parameters": params, "original_llm_output": original_llm_output},
        chat_id=chat_id
    )

    success, result_or_error_dict = await mcp_client.invoke_service(service_name, params)

    await event_emitter.emit(
        event_type="tool_call_end",
        data={"chat_id": chat_id, "tool_type": "MCP", "tool_name": service_name, "success": success,
              "result_or_error": result_or_error_dict},
        chat_id=chat_id
    )

    if success:
        logger.info(f"MCP tool '{service_name}' executed successfully for chat_id '{chat_id}'. Result: {str(result_or_error_dict)[:200]}...")
        return {
            "tool_invocation_result": result_or_error_dict,
            "tool_error": None,
            "parsed_action": None,
            "tool_name_called": service_name,
            "tool_parameters_used": params
        }
    else:
        error_detail = result_or_error_dict.get('error', 'Unknown MCP error')
        logger.error(f"MCP tool '{service_name}' execution failed for chat_id '{chat_id}'. Error: {error_detail}")
        return {
            "tool_invocation_result": None,
            "tool_error": f"MCP tool '{service_name}' failed: {error_detail}",
            "parsed_action": None,
            "tool_name_called": service_name,
            "tool_parameters_used": params
        }

async def execute_rpa_tool_node(state: AgentState, rpa_factory: RPAFactory, rpa_configs: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Executes an RPA tool call based on parsed_action.
    rpa_configs is expected to be a dictionary mapping platform (e.g., "macos", "android")
    to its specific client configuration. This comes from AppSettings.
    Example: rpa_configs = app_settings.get_config("rpa_platforms_config", {})
    """
    chat_id = state.get("chat_id", "unknown_chat")
    parsed_action = state.get("parsed_action")

    if not rpa_factory: # Should not happen if graph is built correctly
        logger.critical(f"RPAFactory not provided to execute_rpa_tool_node for chat_id {chat_id}.")
        return {"tool_error": "RPAFactory is not available.", "parsed_action": None}

    if not rpa_configs:
        logger.warning(f"RPA configurations (rpa_configs) not provided for chat_id {chat_id}. Cannot execute RPA tool.")
        return {"tool_error": "RPA configurations are missing.", "parsed_action": None}

    if not parsed_action or parsed_action.get("type") != "RPA":
        logger.warning(f"execute_rpa_tool_node called with invalid or missing RPA action for chat_id {chat_id}. State: {parsed_action}")
        return {"tool_error": "execute_rpa_tool_node called without a valid RPA action.", "parsed_action": None}

    platform = parsed_action.get("rpa_platform") # Corrected key from "platform" to "rpa_platform"
    script_name = parsed_action.get("name")
    params = parsed_action.get("params", {}) # Should be Dict for execute_workflow
    original_llm_output = parsed_action.get("original_llm_output", "")

    if not script_name:
        logger.error(f"RPA action missing 'name' (script_name) for chat_id {chat_id}. Action: {parsed_action}")
        return {"tool_error": "RPA action is missing the script name.", "parsed_action": None}

    if not platform or platform not in rpa_configs:
        logger.error(f"RPA platform '{platform}' not configured or not supported for chat_id {chat_id}.")
        return {"tool_error": f"RPA platform '{platform}' not configured or unsupported.", "parsed_action": None}

    platform_specific_client_config = rpa_configs[platform]

    logger.info(f"Attempting to get RPA client for platform: '{platform}' for chat_id '{chat_id}'")
    rpa_client: Optional[AbstractRPAClient] = await rpa_factory.get_rpa_client(platform, platform_specific_client_config)

    if not rpa_client:
        logger.error(f"Failed to get/initialize RPA client for platform: '{platform}' for chat_id {chat_id}")
        return {"tool_error": f"Failed to initialize RPA client for '{platform}'.", "parsed_action": None}

    logger.info(f"Executing RPA tool: '{script_name}' on platform '{platform}' with params: {params} for chat_id '{chat_id}'")
    await event_emitter.emit(
        event_type="tool_call_start",
        data={"chat_id": chat_id, "tool_type": "RPA", "platform": platform, "tool_name": script_name, "parameters": params, "original_llm_output": original_llm_output},
        chat_id=chat_id
    )

    # Assuming parsed_action.params is a Dict for execute_workflow as per AbstractRPAClient
    success, result_or_error_str = await rpa_client.execute_workflow(script_name, params)

    await event_emitter.emit(
        event_type="tool_call_end",
        data={"chat_id": chat_id, "tool_type": "RPA", "platform": platform, "tool_name": script_name, "success": success,
              "result_or_error": result_or_error_str},
        chat_id=chat_id
    )

    # Shutdown RPA client - important for clients like Appium that maintain sessions.
    try:
        await rpa_client.shutdown()
        logger.info(f"RPA client for platform '{platform}' shut down after execution for chat_id '{chat_id}'.")
    except Exception as e_shutdown:
        logger.error(f"Error shutting down RPA client for platform '{platform}' for chat_id '{chat_id}': {e_shutdown}", exc_info=True)


    if success:
        logger.info(f"RPA tool '{script_name}' on '{platform}' executed successfully for chat_id '{chat_id}'. Result: {result_or_error_str[:200]}...")
        return {
            "tool_invocation_result": result_or_error_str,
            "tool_error": None,
            "parsed_action": None,
            "tool_name_called": f"RPA:{platform}:{script_name}", # More specific name
            "tool_parameters_used": params
        }
    else:
        logger.error(f"RPA tool '{script_name}' on '{platform}' execution failed for chat_id '{chat_id}'. Error: {result_or_error_str}")
        return {
            "tool_invocation_result": None,
            "tool_error": f"RPA tool '{script_name}' on '{platform}' failed: {result_or_error_str}",
            "parsed_action": None,
            "tool_name_called": f"RPA:{platform}:{script_name}",
            "tool_parameters_used": params
        }
