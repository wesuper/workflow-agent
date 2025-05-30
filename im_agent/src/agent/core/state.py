from typing import Any, Dict, List, Optional, TypedDict, Tuple

class AgentState(TypedDict, total=False): # total=False makes all keys effectively Optional
    """
    Represents the state of the agent's execution graph.
    Using total=False, all fields are considered Optional by TypedDict.
    Nodes in the graph will populate and read from these fields.
    """
    # Input and context from IM
    raw_im_message: Dict[str, Any]
    user_input: str
    platform: str  # e.g., "discord", "wechat_work", "dummy"
    chat_id: str   # Unique identifier for the chat/channel/DM
    user_id: str   # Unique identifier for the user sending the message
    
    # Memory / Conversation History
    # List of messages, e.g., {"role": "user", "content": "Hello"}, {"role": "assistant", "content": "Hi!"}
    conversation_history: List[Dict[str, str]] 
    
    # LLM Interaction
    current_llm_prompt: str # The exact prompt or messages list sent to the LLM
    llm_response_text: str  # Raw text response from LLM
    
    # Parsed Action from LLM
    # This structure helps determine the next step in the graph.
    # 'type': str, e.g., "MCP", "RPA", "ADD_MCP", "REQUEST_TOOLS", "RESPONSE", "CLARIFY", "ERROR"
    # 'name': Optional[str], the service/workflow/tool name.
    # 'params': Optional[Dict[str, Any]], parameters for the tool.
    # 'rpa_platform': Optional[str], e.g., "macos", "android" for RPA actions.
    # 'text_to_user': Optional[str], if the action is to respond directly or ask for clarification.
    # 'tool_type_requested': Optional[str], e.g. "MCP" or "RPA" if type is "REQUEST_TOOLS"
    # 'original_llm_output': str, the raw LLM output string that led to this parsed action.
    parsed_action: Dict[str, Any] 
    
    # Tool information and execution results
    available_mcp_services: List[Dict[str, Any]] # List of MCP service definition dictionaries
    available_rpa_scripts: Dict[str, List[Dict[str, Any]]] # E.g. {"macos": [...], "android": [...]}

    tool_name_called: str # Name of the last tool/service/workflow called
    tool_parameters_used: Dict[str, Any] # Parameters passed to the last tool
    tool_invocation_result: Any # Raw result from the tool
    tool_error: str # Error message if tool execution failed (string summary)
    
    # Output / Response to be sent back to the user
    final_response_to_user: str # The final message content to be sent
    error_message_to_user: str  # An error message to be presented to the user if processing fails
    
    # For more complex agent behaviors (e.g., ReAct, Plan-and-Execute)
    current_task_description: str # Description of the current high-level task
    # List of (action_dict, observation_str_or_dict) tuples
    intermediate_steps: List[Tuple[Dict[str, Any], Any]] 

# Example usage (for testing, not part of the file itself normally):
if __name__ == '__main__':
    # Illustrate how one might use the AgentState TypedDict
    initial_state: AgentState = {
        "user_input": "Hello there!",
        "platform": "dummy",
        "chat_id": "dummy_chat_123",
        "user_id": "user_abc",
        "conversation_history": [{"role": "user", "content": "Hello there!"}]
    }
    print(f"Initial state: {initial_state}")

    initial_state['llm_response_text'] = "Okay, I will search for 'weather in London'."
    initial_state['parsed_action'] = {
        "type": "MCP",
        "name": "OpenWeatherMap_Current",
        "params": {"q": "London,uk", "units": "metric"},
        "original_llm_output": "[ACTION:MCP:OpenWeatherMap_Current:{\"q\": \"London,uk\", \"units\": \"metric\"}]"
    }
    print(f"State after LLM and parsing: {initial_state}")

    initial_state['tool_name_called'] = "OpenWeatherMap_Current"
    initial_state['tool_parameters_used'] = {"q": "London,uk", "units": "metric"}
    initial_state['tool_invocation_result'] = {"temp": 15, "condition": "Cloudy"}
    initial_state['final_response_to_user'] = "The weather in London is 15°C and cloudy."
    initial_state['conversation_history'].append({"role": "assistant", "content": "The weather in London is 15°C and cloudy."})
    
    print(f"State after tool call and final response generation: {initial_state}")

    # Example of an error state
    error_state: AgentState = {
        "user_input": "Book a flight.",
        "platform": "dummy",
        "chat_id": "dummy_chat_456",
        "user_id": "user_def",
        "conversation_history": [{"role": "user", "content": "Book a flight."}],
        "llm_response_text": "[ACTION:MCP:FlightBooking:{\"destination\": \"Paris\"}]", # Missing origin
        "parsed_action": {
            "type": "MCP", 
            "name": "FlightBooking", 
            "params": {"destination": "Paris"}, 
            "original_llm_output": "[ACTION:MCP:FlightBooking:{\"destination\": \"Paris\"}]"
        },
        "tool_name_called": "FlightBooking",
        "tool_parameters_used": {"destination": "Paris"},
        "tool_error": "Missing required parameter: origin_airport",
        "error_message_to_user": "I can't book a flight to Paris without knowing where you're flying from. Could you please provide the departure city or airport?"
    }
    print(f"Example error state: {error_state}")
