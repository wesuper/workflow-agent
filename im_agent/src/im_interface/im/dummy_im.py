import asyncio
import logging
import time
import random
from typing import Any, Callable, Dict, Optional

from .base import IMInterface

logger = logging.getLogger(__name__)

class DummyIMAdapter(IMInterface):
    def __init__(self, platform_name: str, config: Dict[str, Any], on_message_callback: Callable[[Dict[str, Any]], Any]):
        super().__init__(platform_name, config, on_message_callback)
        self.is_connected = False
        self.simulated_message_interval_seconds = self.config.get("simulated_message_interval_seconds", 15)
        self._listen_task: Optional[asyncio.Task] = None
        logger.info(f"[{self.platform_name}] DummyIMAdapter initialized. Message interval: {self.simulated_message_interval_seconds}s")

    async def connect(self) -> bool:
        logger.info(f"[{self.platform_name}] Attempting to connect...")
        await asyncio.sleep(0.1) # Simulate connection delay
        self.is_connected = True
        logger.info(f"[{self.platform_name}] Successfully connected.")
        return True

    async def disconnect(self) -> None:
        logger.info(f"[{self.platform_name}] Disconnecting...")
        if self._listen_task and not self._listen_task.done():
            self._listen_task.cancel()
            try:
                await self._listen_task
            except asyncio.CancelledError:
                logger.info(f"[{self.platform_name}] Listening task cancelled.")
        self.is_connected = False
        await asyncio.sleep(0.1) # Simulate disconnection delay
        logger.info(f"[{self.platform_name}] Successfully disconnected.")

    async def send_message(self, recipient_id: str, message_content: str, message_type: str = "text") -> bool:
        if not self.is_connected:
            logger.warning(f"[{self.platform_name}] Cannot send message. Not connected.")
            return False
        logger.info(f"[{self.platform_name}] Sending message to {recipient_id} (Type: {message_type}): '{message_content}'")
        await asyncio.sleep(0.05) # Simulate send delay
        return True

    def _parse_message(self, raw_message: Any) -> Optional[Dict[str, Any]]:
        """
        For DummyIM, the raw_message is expected to be a pre-formatted dict.
        We'll just add/ensure the platform name.
        """
        if isinstance(raw_message, dict) and "text" in raw_message and "user_id" in raw_message:
            parsed = {
                "platform": self.platform_name,
                "user_name": raw_message.get("user_name", f"DummyUser_{raw_message.get('user_id', 'Unknown')}"),
                "chat_id": raw_message.get("chat_id", raw_message.get("user_id")),
                "message_id": raw_message.get("message_id", f"dummy_msg_{int(time.time() * 1000)}_{random.randint(1000,9999)}"),
                "is_private_chat": raw_message.get("is_private_chat", True),
                "is_mention": raw_message.get("is_mention", False),
                "timestamp": raw_message.get("timestamp", time.time()), # Store as float, can be formatted later
                **raw_message # ensure all original fields are there, platform might be overwritten
            }
            parsed["platform"] = self.platform_name # Ensure platform is correct
            return parsed
        logger.warning(f"[{self.platform_name}] Unparseable or ignorable raw message in DummyIM: {raw_message}")
        return None

    async def _simulate_message_reception(self):
        """Simulates receiving a message."""
        if not self.is_connected:
            logger.debug(f"[{self.platform_name}] Not connected, skipping message simulation.")
            return

        message_type_roll = random.random()
        user_id = f"dummy_user_{random.randint(1, 10)}"
        chat_id = user_id # Default to private chat
        is_private_chat = True
        is_mention = False
        
        simulated_text = f"This is a simulated message from {user_id} on {self.platform_name} at {time.strftime('%Y-%m-%d %H:%M:%S')}."

        if message_type_roll < 0.3: # Simulate a group message where agent is mentioned
            chat_id = f"dummy_group_{random.randint(1, 3)}"
            is_private_chat = False
            is_mention = True
            simulated_text = f"@AgentName {simulated_text} (This was a mention in group {chat_id})"
        elif message_type_roll < 0.6: # Simulate a group message without mention
            chat_id = f"dummy_group_{random.randint(1, 3)}"
            is_private_chat = False
            is_mention = False
            simulated_text = f"{simulated_text} (This was a group message in {chat_id})"
        # Else: it's a private message (defaults)

        simulated_message = {
            # platform will be added by _parse_message
            "user_id": user_id,
            "user_name": f"Dummy {user_id.replace('_', ' ').title()}",
            "chat_id": chat_id,
            "message_id": f"sim_msg_{int(time.time())}_{random.randint(1000,9999)}",
            "text": simulated_text,
            "is_private_chat": is_private_chat,
            "is_mention": is_mention,
            "timestamp": time.time() # Using float timestamp, can be formatted to ISO string if needed by callback
        }
        logger.info(f"[{self.platform_name}] Simulating incoming message: {simulated_message['text']}")
        await self._handle_incoming_message(simulated_message)


    async def start_listening(self) -> None:
        if not self.is_connected:
            logger.error(f"[{self.platform_name}] Cannot start listening. Not connected.")
            # Optionally, raise an error or try to connect first.
            # await self.connect() # Example: try to connect if not connected
            # if not self.is_connected: return
            return

        logger.info(f"[{self.platform_name}] Starting to listen for messages every {self.simulated_message_interval_seconds} seconds...")
        try:
            while self.is_connected: # Loop as long as we are "connected"
                await asyncio.sleep(self.simulated_message_interval_seconds)
                await self._simulate_message_reception()
        except asyncio.CancelledError:
            logger.info(f"[{self.platform_name}] Listening loop cancelled.")
            # self.is_connected = False # Ensure state reflects cancellation
        except Exception as e:
            logger.error(f"[{self.platform_name}] Error in listening loop: {e}", exc_info=True)
            self.is_connected = False # Stop listening on unexpected error
        finally:
            logger.info(f"[{self.platform_name}] Stopped listening.")


if __name__ == '__main__':
    # Example Usage
    logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

    async def dummy_message_handler(message: Dict[str, Any]):
        logger.info(f"MAIN_CALLBACK_HANDLER received message: {message}")

    dummy_config = {
        "enabled": True,
        "simulated_message_interval_seconds": 5 # Faster for testing
    }

    adapter = DummyIMAdapter(platform_name="TestDummy", config=dummy_config, on_message_callback=dummy_message_handler)

    async def main_test_loop():
        if await adapter.connect():
            # Start listening in a background task
            adapter._listen_task = asyncio.create_task(adapter.start_listening())
            
            # Simulate some activity
            await adapter.send_message("user123", "Hello from the main test!")
            await asyncio.sleep(dummy_config["simulated_message_interval_seconds"] * 2 + 1) # Wait for a couple of simulated messages
            
            await adapter.send_message("user456", "Another message before shutdown.")
            await asyncio.sleep(1)

            await adapter.disconnect() # This should also stop the listening task
        else:
            logger.error("Failed to connect to DummyIMAdapter.")

    try:
        asyncio.run(main_test_loop())
    except KeyboardInterrupt:
        logger.info("Test interrupted by user.")
        # Ensure graceful shutdown if asyncio.run was interrupted directly
        # This might require more sophisticated signal handling in a real app
        if adapter and adapter.is_connected: # If test was stopped before disconnect
             asyncio.run(adapter.disconnect())


    logger.info("DummyIMAdapter test finished.")
