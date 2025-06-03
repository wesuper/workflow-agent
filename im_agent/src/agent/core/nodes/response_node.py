import logging
from typing import Dict, Any, Optional # Added Optional

# Corrected relative imports
from ..state import AgentState
from ...memory.manager import MemoryManager
from ...api.event_emitter import event_emitter

logger = logging.getLogger(__name__)

async def format_response_node(state: AgentState, memory_manager: Optional[MemoryManager]) -> Dict[str, Any]:
    """
    Formats the final response to be sent to the user based on the current state
    (e.g., direct LLM response, error message, or a message indicating completion if no specific text).
    Saves the agent's final response to the short-term conversation history.
    """
    chat_id = state.get("chat_id", "unknown_chat")
    user_id = state.get("user_id", "unknown_user") # For logging/event context
    platform = state.get("platform", "unknown_platform") # For logging/event context

    final_reply_text: Optional[str] = None
    parsed_action = state.get("parsed_action")

    # Determine the final reply text based on priority:
    # 1. An explicit error message intended for the user.
    # 2. Text from a "RESPONSE" type parsed_action (usually a direct LLM reply).
    # 3. If a tool executed successfully but produced no specific text for the user,
    #    a generic success message might be warranted (though often the LLM summarizes tool output).
    # 4. If a tool error occurred and wasn't translated into error_message_to_user.
    # 5. A final fallback if no other conditions are met.

    if state.get("error_message_to_user"):
        final_reply_text = state["error_message_to_user"]
        logger.info(f"Using 'error_message_to_user' for final reply to chat_id '{chat_id}': {final_reply_text}")
    elif parsed_action and parsed_action.get("type") == "RESPONSE":
        final_reply_text = parsed_action.get("text_to_user")
        if not final_reply_text: # Should not happen if parser works correctly for RESPONSE type
            final_reply_text = "I've processed that, but I don't have a specific text response."
            logger.warning(f"RESPONSE action for chat_id '{chat_id}' had no 'text_to_user'. Defaulting reply.")
        else:
            logger.info(f"Using 'text_to_user' from RESPONSE action for final reply to chat_id '{chat_id}'.")
    elif state.get("tool_invocation_result") is not None and not state.get("tool_error"):
        # This case implies a tool ran successfully, but the result wasn't processed by LLM again.
        # Usually, tool results go back to LLM. If graph ends here, we need a generic message.
        tool_name = state.get("tool_name_called", "A tool")
        final_reply_text = f"{tool_name} executed successfully." # Simple acknowledgement
        logger.info(f"Tool '{tool_name}' for chat_id '{chat_id}' succeeded, using generic success message as no LLM re-processing occurred.")
    elif state.get("tool_error"):
        # This means a tool failed, and the error wasn't already packaged into error_message_to_user
        tool_name = state.get("tool_name_called", "A tool")
        final_reply_text = f"Sorry, there was an error when I tried to use {tool_name}: {state['tool_error']}"
        logger.warning(f"Using 'tool_error' for final reply to chat_id '{chat_id}': {final_reply_text}")
    else:
        final_reply_text = "I'm not sure how to respond to that. Could you try rephrasing?"
        logger.warning(f"format_response_node reached fallback reply for chat_id '{chat_id}'. Current state might be incomplete. LLM Response: {state.get('llm_response_text')}")

    if not final_reply_text: # Absolute fallback
        final_reply_text = "I'm sorry, an unexpected issue occurred and I don't have a response."
        logger.error(f"Critical: final_reply_text was None or empty at absolute fallback for chat_id '{chat_id}'.")

    # Save agent's response to history
    if memory_manager and chat_id != "unknown_chat" and user_id != "unknown_user": # Ensure memory_manager is provided
        try:
            await memory_manager.add_to_short_term_memory(
                chat_id,
                {"role": "assistant", "content": final_reply_text}
            )
            logger.debug(f"Agent's final response saved to STM for chat_id '{chat_id}'.")
        except Exception as e_mem:
            logger.error(f"Failed to save agent's response to STM for chat_id '{chat_id}': {e_mem}", exc_info=True)
    elif not memory_manager:
        logger.warning(f"MemoryManager not provided to format_response_node. Cannot save agent response for chat_id '{chat_id}'.")

    await event_emitter.emit(
        event_type="agent_response_generated",
        data={
            "chat_id": chat_id,
            "user_id": user_id,
            "platform": platform,
            "message": final_reply_text,
            "is_final_response": True # Indicates this is the response to be sent to user
        },
        chat_id=chat_id # For targeted event if ws_manager supports it
    )

    logger.info(f"Formatted final response for chat_id '{chat_id}' on platform '{platform}': '{final_reply_text[:200]}...'")

    # This node's primary job is to set 'final_response_to_user'.
    # It could also clear other fields if they are considered "consumed" by this point.
    return {
        "final_response_to_user": final_reply_text,
        "parsed_action": None, # Action has been handled or resulted in this response
        "llm_response_text": None, # Consumed
        "tool_invocation_result": None, # Consumed by LLM or by this node
        "tool_error": None, # Consumed by LLM or by this node
        "error_message_to_user": None # Consumed by this node
    }
