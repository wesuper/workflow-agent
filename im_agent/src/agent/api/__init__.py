# __init__.py for the agent API module

from .rest_api import app  # FastAPI app instance
from .websocket_manager import ws_manager, websocket_endpoint # WebSocket connection manager and example endpoint
from .event_emitter import event_emitter # Global event emitter instance

# Add the WebSocket endpoint to the FastAPI app router
# This ensures the /ws/agent_events path is handled by our WebSocket logic.
app.add_api_websocket_route("/ws/agent_events", websocket_endpoint)


__all__ = [
    "app",
    "ws_manager",
    "event_emitter",
    "websocket_endpoint" # Exporting if it needs to be imported elsewhere, though app.add_api_route is common
]
