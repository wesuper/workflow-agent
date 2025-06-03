# __init__.py for the agent's core module

# Import and expose key components from the core module
from .state import AgentState
from .main_graph import create_agent_graph # Added graph creation function
# from .nodes import ( ... ) # Nodes are typically used by the graph, not directly exported from core usually
# from .graph_manager import GraphManager # Example: when graph manager is defined

__all__ = [
    "AgentState",
    "create_agent_graph", # Export the graph factory
    # Add other core component names here as they are created
]
