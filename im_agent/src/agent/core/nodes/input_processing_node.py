import logging
from typing import Dict, Any, List

# Adjust relative imports based on the final directory structure
# Assuming 'state' is in 'core' and 'memory' is a sibling of 'core' under 'agent'
# And 'api' is a sibling of 'agent' under 'src'
# Corrected paths assuming 'nodes' is under 'core'
from ..state import AgentState
from ...memory.manager import MemoryManager
from ...api.event_emitter import event_emitter

logger = logging.getLogger(__name__)

async def process_im_message_node(state: AgentState, memory_manager: MemoryManager) -> Dict[str, Any]:
    """
    Processes the raw IM message from the state, updates conversation history,
    emits an event, and prepares essential fields for the next steps in the graph.

    Args:
        state: The current AgentState, expected to contain 'raw_im_message'.
        memory_manager: An instance of MemoryManager to handle conversation history.

    Returns:
        A dictionary containing updates to the AgentState, including:
        - user_input, platform, chat_id, user_id (extracted from raw_im_message)
        - updated conversation_history (with the new user message appended)
        - current_task_description (set based on the user input)
    """
    raw_message = state.get("raw_im_message") # raw_im_message is already Dict[str, Any] from AgentState
    if not raw_message:
        logger.error("No 'raw_im_message' found in state for input processing.")
        # This is a critical error for this node, should ideally not happen if graph starts correctly.
        # Return an error state or raise an exception. For now, returning minimal state.
        return {
            "user_input": "",
            "platform": "unknown",
            "chat_id": "unknown",
            "user_id": "unknown",
            "conversation_history": [],
            "error_message_to_user": "Critical error: No input message received by agent."
        }

    logger.info(f"Processing IM message for chat_id '{raw_message.get('chat_id')}': {raw_message.get('message', '')[:50]}...")

    user_input = raw_message.get("message", "")
    platform = raw_message.get("platform", "unknown_platform")
    chat_id = raw_message.get("chat_id", "unknown_chat_id") # Should always be present if raw_message is valid
    user_id = raw_message.get("user_id", "unknown_user_id") # Should always be present

    # Emit event about message reception
    await event_emitter.emit(
        event_type="im_message_received",
        data={"user_id": user_id, "platform": platform, "text": user_input, "chat_id": chat_id},
        chat_id=chat_id # For targeted event if ws_manager supports it
    )

    # Retrieve current conversation history
    # The type hint for conversation_history in AgentState is List[Dict[str, str]], not Optional.
    # So, it should always be present, even if empty.
    # If memory_manager.get_short_term_memory can return None, handle it.
    # Assuming get_short_term_memory always returns a list (empty if no history).
    current_history: List[Dict[str, str]] = await memory_manager.get_short_term_memory(chat_id)

    # Add current user message to history
    current_history.append({"role": "user", "content": user_input})

    # Persist the updated history (important!)
    # The current MemoryInterface.add_to_short_term_memory appends.
    # If get_short_term_memory returns a copy, we need to ensure the MemoryManager's internal state is updated.
    # The current design of MemoryManager.add_to_short_term_memory handles appending directly.
    # So, the above append to current_history is for the *next* LLM call in *this turn*.
    # The actual persistent update to STM happens here:
    await memory_manager.add_to_short_term_memory(chat_id, {"role": "user", "content": user_input})

    logger.debug(f"History for chat_id '{chat_id}' after adding new user message: {current_history}")

    return {
        "user_input": user_input,
        "platform": platform,
        "chat_id": chat_id,
        "user_id": user_id,
        "conversation_history": current_history, # This is the history for the *current* LLM call
        "current_task_description": f"Processing user input from {platform}:{user_id} in chat {chat_id}: '{user_input[:100]}'",
        "raw_im_message": None, # Consume the raw message once processed
        "tool_invocation_result": None, # Clear previous tool results at the start of a new user message cycle
        "tool_error": None,
        "tool_name_called": None,
        "tool_parameters_used": None,
        "llm_response_text": None,
        "parsed_action": None,
        "final_response_to_user": None,
        "error_message_to_user": None,
    }
