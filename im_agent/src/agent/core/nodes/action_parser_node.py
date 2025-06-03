import json
import re
import logging
from typing import Dict, Any, Optional

# Corrected relative imports
from ..state import AgentState
from ...api.event_emitter import event_emitter

logger = logging.getLogger(__name__)

# Define regular expressions for parsing actions
# ACTION:MCP:<service_name>:<json_parameters_string>
ACTION_MCP_RE = re.compile(r"^\s*\[ACTION:MCP:([^:]+):(.+)\]\s*$", re.IGNORECASE | re.DOTALL)
# ACTION:RPA:<platform>:<script_name>:<json_arguments_string>
ACTION_RPA_RE = re.compile(r"^\s*\[ACTION:RPA:([^:]+):([^:]+):(.+)\]\s*$", re.IGNORECASE | re.DOTALL)
# ACTION:ADD_MCP:<json_config_string>
ACTION_ADD_MCP_RE = re.compile(r"^\s*\[ACTION:ADD_MCP:(.+)\]\s*$", re.IGNORECASE | re.DOTALL)
# REQUEST:LIST_MCP_SERVICES or REQUEST:LIST_RPA_SCRIPTS
REQUEST_TOOLS_RE = re.compile(r"^\s*\[REQUEST:(LIST_MCP_SERVICES|LIST_RPA_SCRIPTS(?::(macos|android))?)\]\s*$", re.IGNORECASE)

async def parse_llm_action_node(state: AgentState) -> Dict[str, Any]:
    """Parses the LLM response text to identify actions or direct replies."""
    llm_response = state.get("llm_response_text", "").strip()
    chat_id = state.get("chat_id", "unknown_chat") # Get chat_id for event emitting
    user_id = state.get("user_id", "unknown_user") # For ADD_MCP user context

    parsed_action_dict: Optional[Dict[str, Any]] = None
    error_message: Optional[str] = None

    # Ensure llm_response is a string
    if not isinstance(llm_response, str):
        logger.warning(f"LLM response is not a string: {type(llm_response)}. Treating as no action.")
        llm_response = str(llm_response) # Attempt to cast, or handle as error response

    mcp_match = ACTION_MCP_RE.fullmatch(llm_response)
    rpa_match = ACTION_RPA_RE.fullmatch(llm_response)
    add_mcp_match = ACTION_ADD_MCP_RE.fullmatch(llm_response)
    request_tools_match = REQUEST_TOOLS_RE.fullmatch(llm_response)

    try:
        if mcp_match:
            service_name = mcp_match.group(1).strip()
            params_json_str = mcp_match.group(2).strip()
            params = json.loads(params_json_str)
            parsed_action_dict = {"type": "MCP", "name": service_name, "params": params, "original_llm_output": llm_response}
        elif rpa_match:
            platform = rpa_match.group(1).strip().lower()
            script_name = rpa_match.group(2).strip()
            args_json_str = rpa_match.group(3).strip()
            args = json.loads(args_json_str)
            if platform not in ["macos", "android"]:
                error_message = f"Invalid RPA platform specified: {platform}. Must be 'macos' or 'android'."
            else:
                parsed_action_dict = {"type": "RPA", "rpa_platform": platform, "name": script_name, "params": args, "original_llm_output": llm_response}
        elif add_mcp_match:
            config_json_str = add_mcp_match.group(1).strip()
            config = json.loads(config_json_str)
            parsed_action_dict = {"type": "ADD_MCP", "config": config, "user_id": user_id, "original_llm_output": llm_response}
        elif request_tools_match:
            request_type = request_tools_match.group(1).strip() # LIST_MCP_SERVICES or LIST_RPA_SCRIPTS or LIST_RPA_SCRIPTS:platform
            rpa_platform_specific = request_tools_match.group(3) # Optional platform for RPA

            if request_type.startswith("LIST_MCP_SERVICES"):
                tool_type = "MCP"
            elif request_type.startswith("LIST_RPA_SCRIPTS"):
                tool_type = "RPA"
            else: # Should not happen with current regex but good for safety
                error_message = f"Unknown tool request type: {request_type}"
                tool_type = "UNKNOWN"

            parsed_action_dict = {"type": "REQUEST_TOOLS", "tool_type": tool_type, "original_llm_output": llm_response}
            if rpa_platform_specific:
                parsed_action_dict["rpa_platform"] = rpa_platform_specific.lower()

        else:
            # Default to direct response if no specific action pattern is matched
            parsed_action_dict = {"type": "RESPONSE", "text_to_user": llm_response, "original_llm_output": llm_response}

    except json.JSONDecodeError as e:
        logger.error(f"JSON parsing error in LLM response action string for chat_id '{chat_id}': {e}. Response: '{llm_response}'")
        error_message = f"LLM provided an action with invalid JSON content: {str(e)}"
    except Exception as e: # Catch any other parsing errors
        logger.error(f"Error parsing LLM response action string for chat_id '{chat_id}': {e}. Response: '{llm_response}'", exc_info=True)
        error_message = f"Could not parse the action from LLM response: {str(e)}"

    # If there was an error during parsing an intended action string
    if error_message:
        # Fallback: treat the original LLM response as a direct message to the user,
        # but also include the error information for debugging and potential user notification.
        parsed_action_dict = {
            "type": "RESPONSE",
            "text_to_user": llm_response, # Send original LLM text back
            "original_llm_output": llm_response,
            # "parsing_error_for_agent": error_message # Internal note of parsing error
        }
        # The error_message_to_user field in state should be set by a dedicated error handling node if this response is problematic
        # For now, this node focuses on parsing. If parsing fails, it defaults to RESPONSE type.
        # The 'tool_error' field can be used by subsequent nodes to understand if parsing an action failed.
        output_state_update = {"parsed_action": parsed_action_dict, "tool_error": error_message}
    else:
        output_state_update = {"parsed_action": parsed_action_dict, "tool_error": None} # Clear any previous tool_error if parsing is successful now

    await event_emitter.emit(
        event_type="llm_action_parsed",
        data={"chat_id": chat_id,
              "parsed_action_type": parsed_action_dict.get("type") if parsed_action_dict else "None",
              "has_error": bool(error_message)},
        chat_id=chat_id
    )

    logger.info(f"Parsed LLM action for chat_id '{chat_id}': Type='{parsed_action_dict.get('type') if parsed_action_dict else 'None'}'")
    return output_state_update
