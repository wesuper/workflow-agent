import functools
import logging
from typing import Any, Dict, Optional

from langgraph.graph import StateGraph, END

from .state import AgentState
from .nodes import (
    process_im_message_node,
    prepare_llm_request_node,
    call_llm_node,
    parse_llm_action_node, # Added
    list_mcp_services_node, # Added
    list_rpa_scripts_node,  # Added
    execute_mcp_tool_node,  # Added
    execute_rpa_tool_node,  # Added
    format_response_node    # Added
)

# Corrected import paths for clients and managers
from ...tools.llm.base import AbstractLLMClient
from ...memory.manager import MemoryManager
from ...tools.mcp.base import AbstractMCPClient # Added
from ...tools.rpa.factory import RPAFactory     # Added
# from ...api.event_emitter import event_emitter # Not directly used in graph construction

logger = logging.getLogger(__name__)

# --- Conditional Routing Functions ---

def route_after_llm_action_parsing(state: AgentState) -> str:
    """
    Determines the next step based on the parsed LLM action.
    """
    parsed_action = state.get("parsed_action", {})
    action_type = parsed_action.get("type")
    tool_error_from_parsing = state.get("tool_error") # Check if parsing itself set an error

    logger.debug(f"Routing after LLM parse. Action type: '{action_type}', Parsing error: '{tool_error_from_parsing}'")

    if tool_error_from_parsing and action_type == "RESPONSE": # Parsing failed, LLM output is in 'text_to_user' of RESPONSE
        logger.warning(f"LLM response parsing failed: {tool_error_from_parsing}. Defaulting to format_response for original LLM output.")
        return "format_response" # Let format_response handle showing the (potentially flawed) LLM output.

    if action_type == "REQUEST_TOOLS":
        tool_to_list = parsed_action.get("tool_type")
        if tool_to_list == "MCP":
            logger.info("Routing to: list_mcp_services")
            return "list_mcp_services"
        if tool_to_list == "RPA":
            logger.info("Routing to: list_rpa_scripts")
            return "list_rpa_scripts"
        logger.warning(f"Unknown tool type for REQUEST_TOOLS: {tool_to_list}. Defaulting to format_response.")
        # state["error_message_to_user"] = f"I tried to list tools, but couldn't identify which type: {tool_to_list}" # Can't modify state here
        return "format_response"
    elif action_type == "MCP":
        logger.info("Routing to: execute_mcp_tool")
        return "execute_mcp_tool"
    elif action_type == "ADD_MCP": # ADD_MCP is also handled by execute_mcp_tool_node if service_name is special
        logger.info("Routing to: execute_mcp_tool (for ADD_MCP)") # Or a dedicated add_mcp_service_node if created
        return "execute_mcp_tool"
    elif action_type == "RPA":
        logger.info("Routing to: execute_rpa_tool")
        return "execute_rpa_tool"
    elif action_type == "RESPONSE":
        logger.info("Routing to: format_response (direct LLM response)")
        return "format_response"
    else:
        logger.warning(f"Unknown or missing action type: '{action_type}'. Defaulting to format_response.")
        # This case implies the LLM response was not a recognized action or direct response.
        # The format_response_node will use the llm_response_text as is, or a fallback.
        # It might be good to set a specific error message here if the state allowed it,
        # but routers should not modify state. The 'format_response' node will handle it.
        return "format_response"

def route_after_tool_execution_or_listing(state: AgentState) -> str:
    """
    Determines the next step after a tool execution or listing.
    If there was a tool error, or if the tool was a listing tool,
    the output needs to be processed by the LLM.
    Otherwise (e.g., simple tool confirmation), it might go to format_response.
    For this version, tool results and listings always go back to LLM.
    """
    tool_error = state.get("tool_error")
    # Check if available_mcp_services or available_rpa_scripts has been populated (tool listing)
    mcp_listed = bool(state.get("available_mcp_services") is not None) # Check for not None, as empty list is valid
    rpa_listed = bool(state.get("available_rpa_scripts") is not None)

    if tool_error:
        logger.info(f"Tool execution/listing resulted in error: '{tool_error}'. Routing to prepare_llm_request.")
        return "prepare_llm_request"
    elif mcp_listed or rpa_listed:
        logger.info("Tool listing successful. Routing to prepare_llm_request for LLM to process the list.")
        return "prepare_llm_request"
    elif state.get("tool_invocation_result") is not None: # Tool executed successfully with a result
        logger.info("Tool execution successful. Routing to prepare_llm_request for LLM to process the result.")
        return "prepare_llm_request"
    else:
        # This case should ideally not be reached if nodes correctly set tool_error or tool_invocation_result.
        # Or if it was a simple action that doesn't need LLM reprocessing (future enhancement).
        logger.warning("Tool execution/listing node did not set error or result, or list. Defaulting to prepare_llm_request.")
        return "prepare_llm_request"


# --- Graph Definition ---

def create_agent_graph(
    llm_client: AbstractLLMClient,
    memory_manager: MemoryManager,
    mcp_client: Optional[AbstractMCPClient], # MCP client is optional
    rpa_factory: Optional[RPAFactory],       # RPA factory is optional
    # Pass the full AppSettings or pre-resolved configs for RPA
    # For nodes needing specific AppSettings values, it's cleaner to pass just those values.
    rpa_platform_configs: Optional[Dict[str, Any]] = None,
    rpa_scripts_config_path: Optional[str] = None
) -> StateGraph:
    """
    Creates and configures the main agent StateGraph.
    """
    graph = StateGraph(AgentState)

    # Bind dependencies to nodes
    bound_process_im_message_node = functools.partial(process_im_message_node, memory_manager=memory_manager)
    bound_call_llm_node = functools.partial(call_llm_node, llm_client=llm_client)

    # For optional clients/configs, handle cases where they might be None if a node strictly requires them.
    # The nodes themselves also have checks.
    bound_list_mcp_services_node = functools.partial(list_mcp_services_node, mcp_client=mcp_client) if mcp_client else list_mcp_services_node
    bound_list_rpa_scripts_node = functools.partial(list_rpa_scripts_node, rpa_scripts_config_path=rpa_scripts_config_path)
    bound_execute_mcp_tool_node = functools.partial(execute_mcp_tool_node, mcp_client=mcp_client) if mcp_client else execute_mcp_tool_node
    bound_execute_rpa_tool_node = functools.partial(execute_rpa_tool_node, rpa_factory=rpa_factory, rpa_configs=rpa_platform_configs) if rpa_factory and rpa_platform_configs else execute_rpa_tool_node

    bound_format_response_node = functools.partial(format_response_node, memory_manager=memory_manager)

    # Add nodes
    graph.add_node("process_im_message", bound_process_im_message_node)
    graph.add_node("prepare_llm_request", prepare_llm_request_node)
    graph.add_node("call_llm", bound_call_llm_node)
    graph.add_node("parse_llm_action", parse_llm_action_node)
    graph.add_node("list_mcp_services", bound_list_mcp_services_node)
    graph.add_node("list_rpa_scripts", bound_list_rpa_scripts_node)
    graph.add_node("execute_mcp_tool", bound_execute_mcp_tool_node)
    graph.add_node("execute_rpa_tool", bound_execute_rpa_tool_node)
    graph.add_node("format_response", bound_format_response_node)
    # graph.add_node("handle_error", handle_error_node) # Future: dedicated error handling node

    # Set entry point
    graph.set_entry_point("process_im_message")

    # Define core edges
    graph.add_edge("process_im_message", "prepare_llm_request")
    graph.add_edge("prepare_llm_request", "call_llm")
    graph.add_edge("call_llm", "parse_llm_action")

    # Conditional routing after LLM action parsing
    graph.add_conditional_edges(
        "parse_llm_action",
        route_after_llm_action_parsing,
        {
            "list_mcp_services": "list_mcp_services",
            "list_rpa_scripts": "list_rpa_scripts",
            "execute_mcp_tool": "execute_mcp_tool",
            "execute_rpa_tool": "execute_rpa_tool",
            "format_response": "format_response",
            # "handle_error": "handle_error_node" # If a dedicated error node exists
        }
    )

    # Edges from tool listing back to LLM for processing the list
    graph.add_edge("list_mcp_services", "prepare_llm_request") # Route back to LLM
    graph.add_edge("list_rpa_scripts", "prepare_llm_request") # Route back to LLM

    # Conditional routing after tool execution
    # For now, all tool executions route back to prepare_llm_request to inform LLM of outcome.
    graph.add_edge("execute_mcp_tool", "prepare_llm_request")
    graph.add_edge("execute_rpa_tool", "prepare_llm_request")
    # An alternative conditional edge for tool execution if some tools could go direct to response:
    # graph.add_conditional_edges(
    #     "execute_mcp_tool",
    #     route_after_tool_execution_or_listing, # This router would decide based on state.tool_error etc.
    #     {"prepare_llm_request": "prepare_llm_request", "format_response": "format_response"}
    # )
    # graph.add_conditional_edges(
    #     "execute_rpa_tool",
    #     route_after_tool_execution_or_listing,
    #     {"prepare_llm_request": "prepare_llm_request", "format_response": "format_response"}
    # )

    # Final response node leads to END
    graph.add_edge("format_response", END)
    # graph.add_edge("handle_error_node", END) # Or error node could go to format_response

    logger.info("Agent graph defined with new nodes and conditional routing.")
    return graph

# Illustrative main block (remove or adapt for actual use in main.py)
if __name__ == '__main__':
    logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    logger.info("Illustrative graph construction test...")

    # Mock dependencies
    class MockLLM(AbstractLLMClient):
        async def initialize(self, config: Dict[str, Any]) -> bool: return True
        async def get_response(self, prompt: str, conversation_history: List[Dict[str, str]]) -> Tuple[bool, str]:
            if "[REQUEST:LIST_MCP_SERVICES]" in prompt: return True, "[REQUEST:LIST_MCP_SERVICES]"
            if "weather in London" in prompt: return True, "[ACTION:MCP:GetWeather:{\"city\": \"London\"}]"
            return True, f"LLM says: {prompt[:50]}"

    class MockMem(MemoryManager):
        def __init__(self): super().__init__({"default_max_history": 10})

    class MockMCP(AbstractMCPClient):
        async def initialize(self, config: Dict[str, Any]) -> bool: return True
        async def invoke_service(self, service_name: str, parameters: Dict[str, Any]) -> Tuple[bool, Dict[str, Any]]:
            return True, {"service": service_name, "params": parameters, "result": "dummy MCP result"}
        async def add_service(self, service_config: Dict[str, Any], user_id: str) -> bool: return True
        async def list_services(self) -> List[Dict[str, Any]]: return [{"name": "GetWeather", "description": "Gets weather"}]

    class MockRPAFactory(RPAFactory): # Assuming RPAFactory itself doesn't need async init
        async def get_rpa_client(self, platform: str, config: Dict[str, Any]) -> Optional[Any]: return None # Mock no RPA client

    # Create graph
    graph_def = create_agent_graph(
        MockLLM(), MockMem(), MockMCP(), MockRPAFactory(),
        rpa_platform_configs={}, rpa_scripts_config_path=None
    )
    logger.info("Graph definition created.")

    # Compile and test (optional)
    # compiled_graph = graph_def.compile()
    # logger.info("Graph compiled.")
    # async def run_test():
    #     res = await compiled_graph.ainvoke({"raw_im_message": {"message": "weather in London", "chat_id": "1"}})
    #     print(f"Graph result: {res.get('final_response_to_user')}")
    # asyncio.run(run_test())

    # For visualization:
    try:
        from PIL import Image
        import io
        img_bytes = graph_def.get_graph().draw_mermaid_png()
        with open("updated_agent_graph.png", "wb") as f:
            f.write(img_bytes)
        logger.info("Saved updated agent graph diagram to updated_agent_graph.png")
    except Exception as e:
        logger.warning(f"Could not generate graph diagram (graphviz/PIL needed?): {e}")

    from typing import List, Tuple # For MockLLM if __main__ is uncommented.
    logger.info("main_graph.py illustrative test finished.")
