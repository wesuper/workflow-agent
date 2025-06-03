import logging
from typing import Dict, Any, List, Optional # Added Optional

from ..state import AgentState
# Corrected import paths assuming 'tools' is a sibling of 'core' under 'agent'
from ...tools.llm.base import AbstractLLMClient
from ...api.event_emitter import event_emitter

logger = logging.getLogger(__name__)

# Enhanced System Prompt section
# This can be loaded from a file or AppSettings in a real scenario
# For now, keeping it here for clarity within the node's logic.
# The actual system prompt content was designed in a previous subtask.
# This is a simplified version for constructing the LLM call.
# In a full implementation, the `system_prompt_text` would come from AppSettings.

BASE_SYSTEM_PROMPT = """You are "IM-Agent", a helpful AI assistant. Your goal is to understand user requests and respond appropriately. You can use tools (MCP services, RPA scripts) or chat directly.

**Tool Usage Guidelines:**
- To use an MCP Service: `[ACTION:MCP:<service_name>:<json_parameters_string>]`
- To run an Automator/RPA Workflow: `[ACTION:RPA:<platform>:<workflow_name>:<json_arguments_string>]` (platform is 'macos' or 'android')
- To add an MCP Service (whitelisted users): `[ACTION:ADD_MCP:<json_config_string>]`
- To list available tools: `[REQUEST:LIST_MCP_SERVICES]` or `[REQUEST:LIST_RPA_SCRIPTS]` (or `[REQUEST:LIST_RPA_SCRIPTS:macos]` for specific platform)

**Important:**
- If parameters are missing for a tool, ask clarifying questions first.
- For actions that modify state or are sensitive, confirm with the user or clearly state your intent before outputting the action string.
- If you don't have a tool and cannot fulfill the request, say so politely.
"""

def _format_conversation_history_for_prompt(history: List[Dict[str, str]], max_tokens: int = 3000) -> str:
    if not history:
        return "No previous conversation history."

    formatted_history = []
    current_token_count = 0
    # Iterate in reverse to prioritize recent messages
    for msg in reversed(history):
        msg_str = f"{msg['role']}: {msg['content']}"
        # Simple token estimation (words * ~1.33). Replace with actual tokenizer if needed.
        msg_tokens = len(msg_str.split()) * 4 // 3
        if current_token_count + msg_tokens > max_tokens:
            formatted_history.append("... (history truncated due to length)")
            break
        formatted_history.append(msg_str)
        current_token_count += msg_tokens

    return "\n".join(reversed(formatted_history))


def _format_available_tools_for_prompt(state: AgentState) -> str:
    lines = []
    mcp_services = state.get("available_mcp_services")
    rpa_scripts_by_platform = state.get("available_rpa_scripts") # This is Dict[str, List[Dict]]

    if mcp_services:
        lines.append("\nAvailable MCP Services (sample, names only unless details requested):")
        lines.extend([f"- {service.get('name')}" for service in mcp_services[:5]]) # Show first 5
        if len(mcp_services) > 5:
            lines.append("  (...and more available. Ask to list all if needed.)")

    if rpa_scripts_by_platform:
        for platform, scripts in rpa_scripts_by_platform.items():
            if scripts:
                lines.append(f"\nAvailable RPA Scripts for {platform.upper()} (sample, names only):")
                lines.extend([f"- {script.get('name')}" for script in scripts[:5]]) # Show first 5
                if len(scripts) > 5:
                    lines.append("  (...and more available for this platform.)")

    if not lines:
        return "No specific tool information currently loaded. You can request a list of tools if needed."
    return "\n".join(lines)

def _format_tool_result_for_prompt(state: AgentState) -> str:
    tool_name = state.get("tool_name_called")
    tool_error = state.get("tool_error")
    tool_result = state.get("tool_invocation_result")

    if tool_error:
        return f"Previous Action Attempt: Tool '{tool_name}' failed with error: {tool_error}"
    elif tool_result is not None: # Ensure tool_result is not None explicitly
        # Convert dict/list results to JSON string for cleaner inclusion in prompt
        result_str = json.dumps(tool_result) if isinstance(tool_result, (dict, list)) else str(tool_result)
        # Truncate long results
        max_result_len = 500
        if len(result_str) > max_result_len:
            result_str = result_str[:max_result_len] + "..."
        return f"Previous Action Result: Tool '{tool_name}' returned: {result_str}"
    return "No previous tool action taken in this turn, or the action was a direct reply."

async def prepare_llm_request_node(state: AgentState) -> Dict[str, Any]:
    """
    Prepares the full prompt for the LLM, including system instructions,
    formatted conversation history, available tools (if any), and current user input.
    """
    user_input = state.get("user_input", "")
    chat_id = state.get("chat_id", "unknown_chat") # For logging/eventing

    # Construct the prompt components
    system_prompt = BASE_SYSTEM_PROMPT # In a real app, this might be loaded from AppSettings/config

    conversation_history_list = state.get("conversation_history", [])
    # The history passed to LLM should not include the current user input, as that's provided separately.
    # However, our LLM clients expect history to be a list of dicts, and prompt to be the latest user query.
    # For some LLMs (like OpenAI Chat models), the current user_input is the last item in the 'messages' list.
    # For this node, we'll prepare `current_llm_prompt` as a single string for general LLMs,
    # and `conversation_history` (which includes the latest user message) for chat models.

    # For LLMs that take history + prompt:
    # history_for_prompt_str = _format_conversation_history_for_prompt(conversation_history_list[:-1] if conversation_history_list else [])
    # For LLMs that take a list of "messages" (like OpenAI chat):
    # The full conversation_history (including the latest user message) is what we need.

    formatted_tools = _format_available_tools_for_prompt(state)
    formatted_tool_result = _format_tool_result_for_prompt(state)

    # This is a simplified construction. A more robust version might use a templating engine
    # or specific formatting for different LLM provider APIs.
    # For now, we'll assume the LLM client's get_response can take a "prompt" string (which could be the user_input)
    # and a "conversation_history" list. The system prompt is usually handled by the client itself.
    # This node will prepare the 'current_llm_prompt' as the user_input and pass the history.
    # If the LLM needs a single large prompt string, this logic would need to change.

    # Let's assume current_llm_prompt is just the user_input for now,
    # and the LLM client will prepend system prompts and history.
    # However, the initial design of SYSTEM_PROMPT_TEMPLATE suggests building a full string here.
    # Let's build the full string for current_llm_prompt and also keep conversation_history.
    # The LLM client can then decide what to use.

    full_prompt_str = f"{system_prompt}\n\n{formatted_tools}\n\nConversation History:\n{_format_conversation_history_for_prompt(conversation_history_list)}\n\n{formatted_tool_result}\n\nUser: {user_input}\nAssistant:"

    logger.info(f"Prepared LLM prompt for chat_id '{chat_id}': {full_prompt_str[:500]}...") # Log first 500 chars

    await event_emitter.emit(
        event_type="llm_request_prepared",
        data={"chat_id": chat_id, "prompt_summary": full_prompt_str[:200]}, # Summary for event
        chat_id=chat_id
    )

    # Clear tool list from state after incorporating into prompt,
    # so LLM doesn't see stale lists unless re-requested by a [REQUEST:...] command.
    # This also applies to tool results.
    updates_for_state = {
        "current_llm_prompt": full_prompt_str, # The full prompt string
        "conversation_history": conversation_history_list, # History for LLM client
        "available_mcp_services": None, # Consumed
        "available_rpa_scripts": None,  # Consumed
        # Keep tool_name_called, tool_parameters_used, tool_invocation_result, tool_error
        # so they can be added to history if the LLM's response is a direct reply.
        # They will be cleared by call_llm_node after LLM processes them.
    }
    return updates_for_state


async def call_llm_node(state: AgentState, llm_client: AbstractLLMClient) -> Dict[str, Any]:
    """
    Calls the LLM with the prepared prompt and conversation history.
    Updates state with the LLM's response or an error.
    """
    # The prompt passed to llm_client.get_response depends on the LLM.
    # If it's a chat model, history is primary, and user_input is the last message in history.
    # If it's a completion model, current_llm_prompt (which includes history) is used.
    # AbstractLLMClient.get_response takes (prompt: str, conversation_history: List)
    # Let's assume for chat models, `prompt` argument to get_response is the latest user query,
    # and `conversation_history` is the preceding dialogue.
    # The `current_llm_prompt` in state is the fully compiled string for debugging or for completion models.

    user_input = state.get("user_input", "") # This is the most recent user message
    history_for_client = state.get("conversation_history", [])
    # For chat models, the last message in history_for_client IS the user_input.
    # So, we can pass user_input as prompt and history_for_client[:-1] as history,
    # OR pass "" as prompt and the full history_for_client.
    # The current AbstractLLMClient expects (prompt, history).
    # Let's assume `prompt` is the latest query and `history` is prior context.

    # If history_for_client already includes the latest user_input:
    llm_call_prompt = history_for_client[-1]['content'] if history_for_client and history_for_client[-1]['role'] == 'user' else user_input
    llm_call_history = history_for_client[:-1] if history_for_client and history_for_client[-1]['role'] == 'user' else history_for_client


    chat_id = state.get("chat_id", "unknown_chat")
    logger.info(f"Calling LLM for chat_id '{chat_id}' with prompt: '{llm_call_prompt[:100]}...' and history length {len(llm_call_history)}")

    success, response_or_error = await llm_client.get_response(
        prompt=llm_call_prompt,
        conversation_history=llm_call_history
    )

    # Prepare fields to clear from previous tool calls, as LLM has now processed that info.
    updates_to_clear_tool_fields = {
        "tool_invocation_result": None,
        "tool_error": None,
        "tool_name_called": None,
        "tool_parameters_used": None,
    }

    if success:
        logger.info(f"LLM call successful for chat_id '{chat_id}'. Response: {response_or_error[:200]}...")
        await event_emitter.emit(
            event_type="llm_response_received",
            data={"chat_id": chat_id, "success": True, "response_summary": response_or_error[:200]},
            chat_id=chat_id
        )
        return {
            "llm_response_text": response_or_error,
            **updates_to_clear_tool_fields
        }
    else:
        logger.error(f"LLM call failed for chat_id '{chat_id}': {response_or_error}")
        await event_emitter.emit(
            event_type="llm_response_received",
            data={"chat_id": chat_id, "success": False, "error_message": response_or_error},
            chat_id=chat_id
        )
        # Store the LLM error in a way that can be handled by a subsequent error node or directly sent to user
        return {
            "error_message_to_user": f"I encountered an issue with my thinking process: {response_or_error}",
            "llm_response_text": None, # No valid response text
            **updates_to_clear_tool_fields
        }

# Need to import json for _format_tool_result_for_prompt
import json
