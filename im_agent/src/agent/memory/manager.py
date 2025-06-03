import asyncio
import json
import logging
import os
from collections import deque
from typing import Any, Dict, List, Optional, Deque

from .base import MemoryInterface
from ..api.event_emitter import event_emitter # Corrected import path assuming api is sibling of agent

logger = logging.getLogger(__name__)

class MemoryManager(MemoryInterface):
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self._short_term_memory: Dict[str, Deque[Dict[str, str]]] = {}
        self._long_term_memory_cache: Dict[str, Dict[str, Any]] = {}

        self.config = config if config else {}
        self.default_max_history: int = self.config.get("default_max_history", 20)

        ltm_path_setting = self.config.get("long_term_storage_path")
        if ltm_path_setting:
            if not os.path.isabs(ltm_path_setting):
                ltm_path_setting = os.path.abspath(ltm_path_setting)
            self.long_term_storage_path: Optional[str] = ltm_path_setting

            if not os.path.exists(self.long_term_storage_path):
                try:
                    os.makedirs(self.long_term_storage_path, exist_ok=True)
                    logger.info(f"Created long-term memory storage directory: {self.long_term_storage_path}")
                except OSError as e:
                    logger.error(f"Failed to create LTM directory {self.long_term_storage_path}: {e}. Long-term memory will not persist to disk.")
                    self.long_term_storage_path = None
        else:
            self.long_term_storage_path = None
            logger.warning("No 'long_term_storage_path' provided. Long-term memory will be in-memory only.")

        logger.debug(f"MemoryManager created. Max history: {self.default_max_history}, LTM Path: {self.long_term_storage_path}")

    async def initialize(self) -> bool:
        logger.info(f"MemoryManager initialized. Max history: {self.default_max_history}, LTM Path: {self.long_term_storage_path}")
        return True

    async def get_short_term_memory(self, conversation_id: str, max_messages: Optional[int] = None) -> List[Dict[str, str]]:
        # Using conversation_id as chat_id for event routing
        await event_emitter.emit(
            "memory_access",
            {"action": "read_short_term", "conversation_id": conversation_id, "max_messages_requested": max_messages},
            chat_id=conversation_id
        )
        if conversation_id not in self._short_term_memory:
            return []

        history_deque = self._short_term_memory[conversation_id]
        num_to_return = len(history_deque)
        if max_messages is not None and max_messages >= 0:
            num_to_return = min(num_to_return, max_messages)

        return list(history_deque)[-num_to_return:] if num_to_return > 0 else []

    async def add_to_short_term_memory(self, conversation_id: str, message: Dict[str, str]) -> None:
        if conversation_id not in self._short_term_memory:
            self._short_term_memory[conversation_id] = deque(maxlen=self.default_max_history)
        self._short_term_memory[conversation_id].append(message)

        await event_emitter.emit(
            "memory_access",
            {"action": "write_short_term", "conversation_id": conversation_id, "message_summary": message.get("content", "")[:50]},
            chat_id=conversation_id
        )
        logger.debug(f"Added message to STM for {conversation_id}. New length: {len(self._short_term_memory[conversation_id])}")

    async def clear_short_term_memory(self, conversation_id: str) -> None:
        if conversation_id in self._short_term_memory:
            self._short_term_memory[conversation_id].clear()
            logger.info(f"Cleared short-term memory for conversation_id: {conversation_id}")
            await event_emitter.emit(
                "memory_access",
                {"action": "clear_short_term", "conversation_id": conversation_id},
                chat_id=conversation_id
            )
        else:
            logger.debug(f"No short-term memory found to clear for conversation_id: {conversation_id}")

    def _get_user_ltm_filepath(self, user_id: str) -> Optional[str]:
        if not self.long_term_storage_path:
            return None
        safe_user_id = "".join(c if c.isalnum() or c in ('_', '-') else '_' for c in user_id)
        return os.path.join(self.long_term_storage_path, f"{safe_user_id}.json")

    async def _load_user_ltm(self, user_id: str) -> Dict[str, Any]:
        if user_id in self._long_term_memory_cache:
            return self._long_term_memory_cache[user_id]

        filepath = self._get_user_ltm_filepath(user_id)
        if not filepath: return {}

        if not await asyncio.to_thread(os.path.exists, filepath):
            self._long_term_memory_cache[user_id] = {}
            return {}
        try:
            def read_file_sync(path):
                with open(path, 'r') as f: return json.load(f)
            data = await asyncio.to_thread(read_file_sync, filepath)
            if not isinstance(data, dict):
                logger.error(f"LTM file for user '{user_id}' at {filepath} is not a valid JSON object. Resetting.")
                data = {}
            self._long_term_memory_cache[user_id] = data
            return data
        except Exception:
            logger.error(f"Error loading LTM for user '{user_id}' from {filepath}. Returning empty.", exc_info=True)
            self._long_term_memory_cache[user_id] = {}
            return {}

    async def _save_user_ltm(self, user_id: str) -> bool:
        filepath = self._get_user_ltm_filepath(user_id)
        if not filepath: return False

        user_data = self._long_term_memory_cache.get(user_id, {})
        try:
            def write_file_sync(path, data_to_write):
                os.makedirs(os.path.dirname(path), exist_ok=True)
                with open(path, 'w') as f: json.dump(data_to_write, f, indent=4)
            await asyncio.to_thread(write_file_sync, filepath, user_data)
            return True
        except Exception:
            logger.error(f"Failed to save LTM for user '{user_id}' to {filepath}", exc_info=True)
            return False

    async def get_long_term_memory(self, user_id: str, key: str) -> Optional[Any]:
        # Using user_id as chat_id for event routing if appropriate, or None if event is system-wide
        event_chat_id = user_id
        await event_emitter.emit("memory_access", {"action": "read_long_term_start", "user_id": user_id, "key": key}, chat_id=event_chat_id)

        user_ltm = await self._load_user_ltm(user_id)
        value = user_ltm.get(key)

        await event_emitter.emit("memory_access", {"action": "read_long_term_end", "user_id": user_id, "key": key, "found": (value is not None)}, chat_id=event_chat_id)
        return value

    async def set_long_term_memory(self, user_id: str, key: str, value: Any) -> None:
        event_chat_id = user_id
        user_ltm = await self._load_user_ltm(user_id)
        user_ltm[key] = value
        self._long_term_memory_cache[user_id] = user_ltm
        save_success = await self._save_user_ltm(user_id)

        await event_emitter.emit(
            "memory_access",
            {"action": "write_long_term", "user_id": user_id, "key": key, "save_success": save_success},
            chat_id=event_chat_id
        )

    async def delete_long_term_memory(self, user_id: str, key: str) -> bool:
        event_chat_id = user_id
        user_ltm = await self._load_user_ltm(user_id)
        success_status = False
        if key in user_ltm:
            del user_ltm[key]
            self._long_term_memory_cache[user_id] = user_ltm
            if await self._save_user_ltm(user_id):
                success_status = True

        await event_emitter.emit(
            "memory_access",
            {"action": "delete_long_term", "user_id": user_id, "key": key, "deleted": success_status},
            chat_id=event_chat_id
        )
        return success_status

# Main block from previous version for quick testing (if needed)
if __name__ == '__main__':
    logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    # Mock event_emitter for standalone testing
    class MockEventEmitter:
        async def emit(self, event_type: str, data: Dict[str, Any], chat_id: Optional[str] = None):
            logger.info(f"EVENT: {event_type} (ChatID: {chat_id}) - Data: {data}")
    event_emitter = MockEventEmitter() # type: ignore

    async def test_memory_manager():
        test_ltm_dir = "temp_ltm_storage_test_events"
        if os.path.exists(test_ltm_dir):
            for f in os.listdir(test_ltm_dir): os.remove(os.path.join(test_ltm_dir, f))
            os.rmdir(test_ltm_dir)

        manager_config = {"default_max_history": 3, "long_term_storage_path": test_ltm_dir}
        manager = MemoryManager(config=manager_config)
        await manager.initialize()
        logger.info(f"MemoryManager with LTM path initialized. Path: {manager.long_term_storage_path}")

        convo_id = "event_convo_1"
        await manager.add_to_short_term_memory(convo_id, {"role": "user", "content": "Msg1"})
        await manager.add_to_short_term_memory(convo_id, {"role": "assistant", "content": "Msg2"})
        stm = await manager.get_short_term_memory(convo_id, max_messages=1)
        assert len(stm) == 1

        user_id_ltm = "event_user_1"
        await manager.set_long_term_memory(user_id_ltm, "pref", "blue")
        val = await manager.get_long_term_memory(user_id_ltm, "pref")
        assert val == "blue"
        await manager.delete_long_term_memory(user_id_ltm, "pref")
        val_del = await manager.get_long_term_memory(user_id_ltm, "pref")
        assert val_del is None
        await manager.clear_short_term_memory(convo_id)

        if os.path.exists(test_ltm_dir): # Cleanup
            for f_name in os.listdir(test_ltm_dir): os.remove(os.path.join(test_ltm_dir, f_name))
            os.rmdir(test_ltm_dir)
        logger.info(f"Cleaned up LTM test directory: {test_ltm_dir}")

    # asyncio.run(test_memory_manager()) # Commented out
    logger.info("MemoryManager (with events) example usage finished.")
