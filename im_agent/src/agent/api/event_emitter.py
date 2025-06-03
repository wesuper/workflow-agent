import asyncio
import datetime
import logging
import json # Added for testing block
from typing import Dict, Any, Optional, List # Added Optional, List for testing block

from .websocket_manager import ws_manager

logger = logging.getLogger(__name__)

class EventEmitter:
    """
    A service to emit events to connected WebSocket clients.
    This allows various backend components (e.g., LangGraph nodes, tools)
    to send updates or notifications to the frontend or other listeners.

    Base Event Structure (sent to WebSocket clients):
    {
        "type": str,        # Event type identifier (see specific event types below)
        "timestamp": str,   # ISO 8601 UTC timestamp string
        "chat_id": Optional[str], # For routing or context, if applicable to the event
        "data": Dict[str, Any]    # Event-specific payload (see schemas below)
    }

    --- Known Event Schemas for the 'data' payload ---

    Event Type: "im_message_received"
    Description: Emitted when a new message is received from an IM platform.
    Data:
        {
            "user_id": str,
            "platform": str,
            "text": str,    # The content of the message received
            "chat_id": str  # chat_id is also in the outer envelope for routing
        }

    Event Type: "llm_request_prepared"
    Description: Emitted just before calling the LLM.
    Data:
        {
            "chat_id": str,
            "prompt_summary": str # A summary or first N chars of the prompt sent to LLM
        }

    Event Type: "llm_response_received"
    Description: Emitted after receiving a response (or error) from the LLM.
    Data:
        {
            "chat_id": str,
            "success": bool,
            "response_summary": Optional[str], # Summary or first N chars of LLM response if successful
            "error_message": Optional[str]   # Error details if LLM call failed
        }

    Event Type: "llm_action_parsed"
    Description: Emitted after the LLM's response has been parsed for an action.
    Data:
        {
            "chat_id": str,
            "parsed_action_type": Optional[str], # e.g., "MCP", "RPA", "RESPONSE", "REQUEST_TOOLS"
            "has_error": bool,                 # True if parsing failed or action is an error
            "action_details": Optional[Dict]   # If an action, details like name, params.
                                               # Example: {"name": "service_X", "params": {"p1": "v1"}}
        }

    Event Type: "mcp_services_listed"
    Description: Emitted when MCP services are successfully listed (usually after a [REQUEST:LIST_MCP_SERVICES]).
    Data:
        {
            "chat_id": str,
            "service_count": int,
            "services_sample": Optional[List[Dict]] # e.g., first 3-5 service definitions
        }

    Event Type: "mcp_services_listed_error"
    Description: Emitted if there's an error listing MCP services.
    Data:
        {
            "chat_id": str,
            "error": str # Error message
        }

    Event Type: "rpa_scripts_listed"
    Description: Emitted when RPA scripts are successfully listed.
    Data:
        {
            "chat_id": str,
            "requested_platform": Optional[str], # "macos", "android", or None if all
            "macos_count": int,
            "android_count": int,
            "scripts_sample": Optional[Dict[str, List[Dict]]] # e.g., {"macos": [script1_def, ...]}
        }

    Event Type: "rpa_scripts_listed_error"
    Description: Emitted if there's an error listing RPA scripts.
    Data:
        {
            "chat_id": str,
            "error": str # Error message
        }

    Event Type: "tool_call_start"
    Description: Emitted just before an MCP or RPA tool/script is executed.
    Data:
        {
            "chat_id": str,
            "tool_type": "MCP" | "RPA",
            "tool_name": str,
            "platform": Optional[str], # For RPA: "macos" or "android"
            "parameters": Dict,        # Parameters/arguments for the tool
            "original_llm_output": str # The LLM output string that triggered this tool call
        }

    Event Type: "tool_call_end"
    Description: Emitted after an MCP or RPA tool/script execution attempt.
    Data:
        {
            "chat_id": str,
            "tool_type": "MCP" | "RPA",
            "tool_name": str,
            "platform": Optional[str], # For RPA
            "success": bool,
            "result_or_error": Any     # The direct result from the tool or an error message/dict
        }

    Event Type: "agent_response_generated"
    Description: Emitted when the agent has formulated its final response to be sent to the user.
    Data:
        {
            "chat_id": str,
            "user_id": str,
            "platform": str,
            "message": str,             # The content of the agent's response
            "is_final_response": bool   # True if this is the concluding message for the current interaction
        }

    Event Type: "memory_access"
    Description: Emitted for various memory operations.
    Data:
        {
            "action": "read_short_term" | "write_short_term" | "clear_short_term" |
                      "read_long_term_start" | "read_long_term_end" |
                      "write_long_term" | "delete_long_term",
            "conversation_id": Optional[str], # For STM operations
            "user_id": Optional[str],         # For LTM operations
            "key": Optional[str],             # For LTM key-based operations
            "found": Optional[bool],          # For LTM read_long_term_end
            "message_summary": Optional[str], # For STM write_short_term
            "save_success": Optional[bool],   # For LTM write_long_term
            "deleted": Optional[bool],        # For LTM delete_long_term
            "max_messages_requested": Optional[int] # For STM read_short_term
        }

    --- Future Event Schemas (Conceptual) ---

    Event Type: "planning_start"
    Description: Emitted when the agent starts its planning phase for a user request.
    Data:
        {
            "chat_id": str,
            "user_input": str
        }

    Event Type: "plan_generated"
    Description: Emitted when the agent (LLM or planning logic) generates a plan.
    Data:
        {
            "chat_id": str,
            "plan_id": Optional[str], # A unique ID for the plan if applicable
            "plan_summary": str,      # A human-readable summary of the plan
            "steps": List[Dict[str,Any]] # Detailed steps: {"description": str, "tool": Optional[str], "params": Optional[Dict]}
        }

    Event Type: "tool_selection"
    Description: Emitted when a specific tool is selected for execution as part of a plan.
    Data:
        {
            "chat_id": str,
            "tool_name": str,
            "platform": Optional[str], # if RPA
            "reasoning": Optional[str],    # LLM's rationale for selecting the tool (if available)
            "confidence": Optional[float] # LLM's confidence in this selection (if available)
        }

    Event Type: "tool_call_update"
    Description: Emitted periodically for long-running tools to provide progress updates.
    Data:
        {
            "chat_id": str,
            "tool_name": str,
            "platform": Optional[str],
            "status": str, # e.g., "running", "waiting_for_element", "step_completed"
            "progress_percentage": Optional[float],
            "details": Optional[Dict[str, Any]] # Specific update details
        }

    Event Type: "graph_step_transition"
    Description: Emitted when the LangGraph transitions between nodes (if using a custom callback).
    Data:
        {
            "chat_id": str, # Or thread_id
            "from_node": str,
            "to_node": str,
            "state_keys_changed": List[str],
            # "state_snapshot": Optional[Dict[str, Any]] # Potentially large, use with caution
        }
    """
    async def emit(self, event_type: str, data: Dict[str, Any], chat_id: Optional[str] = None):
        timestamp = datetime.datetime.now(datetime.timezone.utc).isoformat()
        # Ensure chat_id from data (if present) is consistent or add if missing
        event_payload_data = data.copy()
        if 'chat_id' not in event_payload_data and chat_id:
            event_payload_data['chat_id'] = chat_id

        event_payload = {
            "type": event_type,
            "timestamp": timestamp,
            "chat_id": chat_id, # Outer envelope chat_id for routing by ws_manager
            "data": event_payload_data
        }

        logger.debug(f"Emitting event: Type='{event_type}', Target ChatID='{chat_id}', Data='{event_payload_data}'")

        # Use ws_manager's logic for targeted vs broadcast
        target_ws = None
        if chat_id and chat_id in ws_manager.active_connections_by_id:
            target_ws = ws_manager.active_connections_by_id[chat_id]

        if target_ws:
            # logger.debug(f"Sending event personally to client_id/chat_id: {chat_id}")
            await ws_manager.send_personal_json(target_ws, event_payload)
        elif not chat_id: # If no chat_id, broadcast to all general connections
            # logger.debug("Broadcasting event to all connected clients.")
            await ws_manager.broadcast_json(event_payload)
        else: # chat_id provided but no specific websocket connection found for it
            logger.warning(f"Attempted to emit event to specific chat_id '{chat_id}', but no active WebSocket found. Event not sent to specific client.")


# Global instance for the emitter
event_emitter = EventEmitter()

# Example usage block from previous version (can be kept for testing this file directly)
if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)

    class MockWebSocket:
        def __init__(self, client_id="test_client"):
            self.client_id = client_id
            self.accepted = False
            self.sent_data = []
        async def accept(self): self.accepted = True
        async def send_text(self, data_text: str): self.sent_data.append(json.loads(data_text))
        async def close(self): pass

    class MockConnectionManager:
        def __init__(self):
            self.active_connections: List[MockWebSocket] = []
            self.active_connections_by_id: Dict[str, MockWebSocket] = {}
        async def connect(self, websocket: MockWebSocket, client_id: Optional[str] = None):
            await websocket.accept()
            self.active_connections.append(websocket)
            if client_id: self.active_connections_by_id[client_id] = websocket
        def disconnect(self, websocket: MockWebSocket, client_id: Optional[str] = None): pass
        async def broadcast_json(self, data: Dict[str, Any]):
            for ws in self.active_connections: await ws.send_text(json.dumps(data))
        async def send_personal_json(self, websocket: MockWebSocket, data: Dict[str, Any]):
            await websocket.send_text(json.dumps(data))

    async def test_event_emitter():
        global ws_manager
        original_ws_manager = ws_manager
        mock_ws_manager_instance = MockConnectionManager()
        ws_manager = mock_ws_manager_instance # type: ignore

        c1 = MockWebSocket("c1"); await ws_manager.connect(c1, "chat1")
        c2 = MockWebSocket("c2"); await ws_manager.connect(c2) # General connection

        await event_emitter.emit("test_event", {"detail": "hello all"}, chat_id=None)
        assert len(c1.sent_data) == 1 and c1.sent_data[0]["data"]["detail"] == "hello all"
        assert len(c2.sent_data) == 1 and c2.sent_data[0]["data"]["detail"] == "hello all"

        c1.sent_data.clear(); c2.sent_data.clear()
        await event_emitter.emit("user_specific_event", {"info": "for chat1 only"}, chat_id="chat1")
        assert len(c1.sent_data) == 1 and c1.sent_data[0]["data"]["info"] == "for chat1 only"
        assert len(c2.sent_data) == 0

        ws_manager = original_ws_manager # Restore
        logger.info("EventEmitter tests finished.")

    # asyncio.run(test_event_emitter()) # Commented out
    logger.info("EventEmitter (with schemas) example usage finished.")
