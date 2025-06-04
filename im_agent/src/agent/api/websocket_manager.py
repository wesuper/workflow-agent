import asyncio
import json
from fastapi import WebSocket, WebSocketDisconnect
from typing import List, Dict, Any, Set, Optional # Added Optional for type hints
import logging
import datetime # For timestamping events

logger = logging.getLogger(__name__)

class ConnectionManager:
    def __init__(self):
        # Using a set for active_connections can be slightly more efficient for add/remove
        # if connection uniqueness needs to be strictly enforced by object hash,
        # but List is fine for managing WebSocket objects directly.
        self.active_connections: List[WebSocket] = []
        self.active_connections_by_id: Dict[str, WebSocket] = {} # Example: track by chat_id or user_id
        logger.info("ConnectionManager initialized.")

    async def connect(self, websocket: WebSocket, client_id: Optional[str] = None): # client_id can be chat_id or user_id
        await websocket.accept()
        self.active_connections.append(websocket)

        # If a client_id (e.g., chat_id from query params) is provided, track it
        # This allows targeted broadcasts to specific sessions if needed later.
        # For now, client_id is illustrative.
        if client_id:
            self.active_connections_by_id[client_id] = websocket
            logger.info(f"New WebSocket connection: {websocket.client}, ID: {client_id}. Total general connections: {len(self.active_connections)}")
        else:
            logger.info(f"New WebSocket connection: {websocket.client}. Total general connections: {len(self.active_connections)}")


    def disconnect(self, websocket: WebSocket, client_id: Optional[str] = None):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)

        if client_id and client_id in self.active_connections_by_id:
            del self.active_connections_by_id[client_id]
            logger.info(f"WebSocket connection closed: {websocket.client}, ID: {client_id}")
        else:
            logger.info(f"WebSocket connection closed: {websocket.client}")

        logger.info(f"Total general connections remaining: {len(self.active_connections)}")


    async def broadcast_json(self, data: Dict[str, Any]):
        """Broadcasts a JSON message to all active WebSocket connections."""
        if not self.active_connections:
            # logger.debug("No active WebSocket connections to broadcast to.")
            return

        message_str = json.dumps(data)

        # Create a list of tasks for sending messages concurrently
        # Iterate over a copy of the list if disconnections can happen during broadcast
        disconnected_sockets: List[WebSocket] = []
        for conn in list(self.active_connections): # Iterate over a copy
            try:
                await conn.send_text(message_str)
            except WebSocketDisconnect: # Handle if socket disconnected abruptly during broadcast
                logger.warning(f"WebSocket {conn.client} disconnected during broadcast. Removing.")
                disconnected_sockets.append(conn)
            except RuntimeError as e: # Can happen if connection is already closed
                 logger.warning(f"RuntimeError sending to WebSocket {conn.client} (likely already closed): {e}. Removing.")
                 disconnected_sockets.append(conn)
            except Exception as e:
                logger.error(f"Error sending to WebSocket {conn.client}: {e}", exc_info=True)
                # Potentially remove problematic connections, but be careful with modifying list while iterating
                disconnected_sockets.append(conn)

        for ws in disconnected_sockets:
            self.disconnect(ws) # Properly remove them

    async def send_personal_json(self, websocket: WebSocket, data: Dict[str, Any]):
        """Sends a JSON message to a specific WebSocket client."""
        try:
            await websocket.send_text(json.dumps(data))
        except WebSocketDisconnect:
            logger.warning(f"WebSocket {websocket.client} disconnected before personal message could be sent. Removing.")
            self.disconnect(websocket)
        except Exception as e:
            logger.error(f"Error sending personal message to WebSocket {websocket.client}: {e}", exc_info=True)
            self.disconnect(websocket) # Assume connection is problematic

# Global instance for the manager
ws_manager = ConnectionManager()

# This endpoint definition will be imported and added to the FastAPI app
# in api/__init__.py to avoid circular dependencies if rest_api.py needs ws_manager.
async def websocket_endpoint(websocket: WebSocket, chat_id: Optional[str] = None): # Example: chat_id from query param
    """
    Main WebSocket endpoint for agent events.
    A client (e.g., frontend) connects here. The server primarily broadcasts events.
    `chat_id` can be passed as a query parameter, e.g., /ws/agent_events?chat_id=session123
    """
    unique_client_id = chat_id if chat_id else str(websocket.client) # Fallback to host/port if no chat_id
    await ws_manager.connect(websocket, client_id=unique_client_id)

    try:
        # Send a welcome message or initial state if desired
        await ws_manager.send_personal_json(websocket, {
            "type": "connection_ack",
            "message": "Connected to IM-Agent event stream.",
            "client_id": unique_client_id,
            "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat()
        })

        while True:
            # This loop primarily keeps the connection alive.
            # Server -> Client communication is mainly via broadcasts from EventEmitter.
            # We can implement a ping/pong here or handle client messages if needed.
            try:
                # Set a timeout for receive_text to allow periodic checks or pings
                # This makes the server more responsive to shutdown signals if not using a separate ping task.
                received_data = await asyncio.wait_for(websocket.receive_text(), timeout=60.0)
                logger.info(f"Received message from WebSocket client '{unique_client_id}': {received_data}")

                # Echo back or process if client-to-server messages are part of the design
                # For now, mainly for keeping alive or simple commands.
                # Example: if client sends 'ping', server replies 'pong'
                if received_data.lower() == 'ping':
                    await websocket.send_text('pong')

            except asyncio.TimeoutError:
                # No data received, good time to send a server-side ping if desired
                # logger.debug(f"WebSocket {unique_client_id} alive, no message in last 60s.")
                # await websocket.send_text('server_ping') # Example server-side ping
                pass
            except WebSocketDisconnect:
                logger.info(f"WebSocket client '{unique_client_id}' disconnected gracefully.")
                break # Exit loop on disconnect
            except Exception as e: # Catch other errors during receive
                logger.error(f"Error with WebSocket client '{unique_client_id}': {e}", exc_info=True)
                break # Exit loop and disconnect

    except WebSocketDisconnect: # Handles case where client disconnects before/during initial messages
        logger.info(f"WebSocket client '{unique_client_id}' disconnected (outer try).")
    except Exception as e:
        logger.error(f"Unexpected error in WebSocket endpoint for '{unique_client_id}': {e}", exc_info=True)
    finally:
        ws_manager.disconnect(websocket, client_id=unique_client_id)
        logger.info(f"WebSocket connection cleanup for '{unique_client_id}' finished.")
