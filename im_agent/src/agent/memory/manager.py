import asyncio
import json
import logging # Added logging
import os
from collections import deque
from typing import Any, Dict, List, Optional, Deque

from .base import MemoryInterface
# import aiofiles # Option for async file I/O, will use asyncio.to_thread for now

logger = logging.getLogger(__name__) # Added logger

class MemoryManager(MemoryInterface):
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self._short_term_memory: Dict[str, Deque[Dict[str, str]]] = {}
        self._long_term_memory_cache: Dict[str, Dict[str, Any]] = {} 
        
        self.config = config if config else {}
        self.default_max_history: int = self.config.get("default_max_history", 20)
        
        # Ensure long_term_storage_path is resolved correctly if relative
        ltm_path_setting = self.config.get("long_term_storage_path")
        if ltm_path_setting:
            if not os.path.isabs(ltm_path_setting):
                # Assuming relative paths for LTM are from project root or a defined base
                # For simplicity, let's assume it's relative to CWD if not absolute,
                # or that the config pass to __init__ has already resolved it.
                # A common pattern: resolve relative to project root.
                # For now, if relative, it's from current working directory.
                # This should ideally be resolved by the configuration loader.
                ltm_path_setting = os.path.abspath(ltm_path_setting)
            self.long_term_storage_path: Optional[str] = ltm_path_setting
            
            if not os.path.exists(self.long_term_storage_path):
                try:
                    os.makedirs(self.long_term_storage_path, exist_ok=True)
                    logger.info(f"Created long-term memory storage directory: {self.long_term_storage_path}")
                except OSError as e:
                    logger.error(f"Failed to create LTM directory {self.long_term_storage_path}: {e}. Long-term memory will not persist to disk.")
                    self.long_term_storage_path = None # Disable LTM file persistence
        else:
            self.long_term_storage_path = None
            logger.warning("No 'long_term_storage_path' provided. Long-term memory will be in-memory only.")

        logger.info(f"MemoryManager created. Max history: {self.default_max_history}, LTM Path: {self.long_term_storage_path}")

    async def initialize(self) -> bool:
        """Initializes memory manager."""
        logger.info(f"MemoryManager initialized. Max history: {self.default_max_history}, LTM Path: {self.long_term_storage_path}")
        # Could pre-load all user LTMs if desired, but typically loaded on demand.
        return True

    # --- Short-Term Memory ---
    async def get_short_term_memory(self, conversation_id: str, max_messages: Optional[int] = None) -> List[Dict[str, str]]:
        if conversation_id not in self._short_term_memory:
            return []
        
        history_deque = self._short_term_memory[conversation_id]
        
        # Determine how many messages to retrieve
        # The deque already respects its own maxlen (self.default_max_history or specific one if set differently)
        # If max_messages is provided, it acts as a further limit on what's returned from the current deque state.
        num_to_return = len(history_deque)
        if max_messages is not None and max_messages >= 0: # max_messages=0 means return none from this specific request
            num_to_return = min(num_to_return, max_messages)
        
        # Return the most recent 'num_to_return' messages
        return list(history_deque)[-num_to_return:] if num_to_return > 0 else []


    async def add_to_short_term_memory(self, conversation_id: str, message: Dict[str, str]) -> None:
        if conversation_id not in self._short_term_memory:
            # If a conversation_id has specific max_len requirement from config, it could be applied here.
            # For now, all use default_max_history.
            self._short_term_memory[conversation_id] = deque(maxlen=self.default_max_history)
        self._short_term_memory[conversation_id].append(message)
        logger.debug(f"Added message to STM for {conversation_id}. New length: {len(self._short_term_memory[conversation_id])}")

    async def clear_short_term_memory(self, conversation_id: str) -> None:
        if conversation_id in self._short_term_memory:
            self._short_term_memory[conversation_id].clear()
            logger.info(f"Cleared short-term memory for conversation_id: {conversation_id}")
        else:
            logger.debug(f"No short-term memory found to clear for conversation_id: {conversation_id}")

    # --- Long-Term Memory (File-Based per User) ---
    def _get_user_ltm_filepath(self, user_id: str) -> Optional[str]:
        if not self.long_term_storage_path:
            return None
        # Sanitize user_id to be a valid filename component (basic sanitization)
        safe_user_id = "".join(c if c.isalnum() or c in ('_', '-') else '_' for c in user_id)
        return os.path.join(self.long_term_storage_path, f"{safe_user_id}.json")

    async def _load_user_ltm(self, user_id: str) -> Dict[str, Any]:
        if user_id in self._long_term_memory_cache:
            return self._long_term_memory_cache[user_id]

        filepath = self._get_user_ltm_filepath(user_id)
        if not filepath:
            logger.debug(f"LTM filepath not available for user '{user_id}', returning empty LTM cache.")
            return {}

        if not await asyncio.to_thread(os.path.exists, filepath):
            logger.debug(f"LTM file for user '{user_id}' not found at {filepath}. Initializing empty LTM cache for user.")
            self._long_term_memory_cache[user_id] = {}
            return {}

        try:
            logger.debug(f"Loading LTM for user '{user_id}' from {filepath}.")
            def read_file_sync(path):
                with open(path, 'r') as f:
                    return json.load(f)
            
            data = await asyncio.to_thread(read_file_sync, filepath)
            if not isinstance(data, dict): # Ensure content is a dict
                logger.error(f"LTM file for user '{user_id}' at {filepath} does not contain a valid JSON object (dictionary). Resetting LTM for user.")
                data = {}
            self._long_term_memory_cache[user_id] = data
            return data
        except json.JSONDecodeError:
            logger.error(f"Failed to decode JSON from LTM file {filepath} for user '{user_id}'. Returning empty LTM.", exc_info=True)
            self._long_term_memory_cache[user_id] = {} # Initialize to empty on error
            return {}
        except Exception as e:
            logger.error(f"Unexpected error loading LTM file {filepath} for user '{user_id}': {e}", exc_info=True)
            self._long_term_memory_cache[user_id] = {}
            return {}

    async def _save_user_ltm(self, user_id: str) -> bool:
        filepath = self._get_user_ltm_filepath(user_id)
        if not filepath:
            logger.warning(f"LTM filepath not available for user '{user_id}'. Cannot save LTM.")
            return False

        user_data = self._long_term_memory_cache.get(user_id, {})
        logger.debug(f"Saving LTM for user '{user_id}' to {filepath}. Data: {user_data}")
        
        try:
            def write_file_sync(path, data_to_write):
                # Ensure directory exists one last time, though __init__ should handle it.
                os.makedirs(os.path.dirname(path), exist_ok=True)
                with open(path, 'w') as f:
                    json.dump(data_to_write, f, indent=4)
            
            await asyncio.to_thread(write_file_sync, filepath, user_data)
            return True
        except Exception as e:
            logger.error(f"Failed to save LTM file {filepath} for user '{user_id}': {e}", exc_info=True)
            return False

    async def get_long_term_memory(self, user_id: str, key: str) -> Optional[Any]:
        user_ltm = await self._load_user_ltm(user_id)
        return user_ltm.get(key)

    async def set_long_term_memory(self, user_id: str, key: str, value: Any) -> None:
        user_ltm = await self._load_user_ltm(user_id) # Ensures cache is populated if file exists
        user_ltm[key] = value # Update the cache
        self._long_term_memory_cache[user_id] = user_ltm # Ensure it's set if it was empty before
        await self._save_user_ltm(user_id)

    async def delete_long_term_memory(self, user_id: str, key: str) -> bool:
        user_ltm = await self._load_user_ltm(user_id)
        if key in user_ltm:
            del user_ltm[key]
            self._long_term_memory_cache[user_id] = user_ltm # Update cache
            await self._save_user_ltm(user_id)
            return True
        return False

if __name__ == '__main__':
    logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

    async def test_memory_manager():
        # Create a temporary directory for LTM testing
        test_ltm_dir = "temp_ltm_storage_test"
        if os.path.exists(test_ltm_dir):
            # Clean up from previous run if any
            for f in os.listdir(test_ltm_dir): os.remove(os.path.join(test_ltm_dir, f))
            os.rmdir(test_ltm_dir)
        
        # Test with LTM path
        manager_config = {
            "default_max_history": 5,
            "long_term_storage_path": test_ltm_dir
        }
        manager = MemoryManager(config=manager_config)
        init_status = await manager.initialize()
        assert init_status
        logger.info(f"MemoryManager with LTM path initialized. Path: {manager.long_term_storage_path}")

        # Short-Term Memory Tests
        convo_id = "test_convo_123"
        await manager.add_to_short_term_memory(convo_id, {"role": "user", "content": "Hello"})
        await manager.add_to_short_term_memory(convo_id, {"role": "assistant", "content": "Hi there!"})
        stm = await manager.get_short_term_memory(convo_id)
        logger.info(f"STM for {convo_id}: {stm}")
        assert len(stm) == 2
        assert stm[1]["content"] == "Hi there!"

        # Test max_messages for STM
        stm_limited = await manager.get_short_term_memory(convo_id, max_messages=1)
        logger.info(f"STM limited for {convo_id}: {stm_limited}")
        assert len(stm_limited) == 1
        assert stm_limited[0]["content"] == "Hi there!" # Gets the most recent

        # Test STM maxlen
        for i in range(10): # Add 10 more messages
            await manager.add_to_short_term_memory(convo_id, {"role": "user", "content": f"Message {i+1}"})
        stm_maxlen_test = await manager.get_short_term_memory(convo_id)
        logger.info(f"STM after 10 more messages (maxlen {manager.default_max_history}): {stm_maxlen_test}")
        assert len(stm_maxlen_test) == manager.default_max_history # Should be capped at 5

        await manager.clear_short_term_memory(convo_id)
        stm_cleared = await manager.get_short_term_memory(convo_id)
        logger.info(f"STM after clear for {convo_id}: {stm_cleared}")
        assert len(stm_cleared) == 0

        # Long-Term Memory Tests
        user_id_ltm = "user_ltm_test_789"
        await manager.set_long_term_memory(user_id_ltm, "preference_theme", "dark")
        await manager.set_long_term_memory(user_id_ltm, "last_location", {"city": "Testville"})
        
        theme = await manager.get_long_term_memory(user_id_ltm, "preference_theme")
        logger.info(f"LTM: User '{user_id_ltm}' theme: {theme}")
        assert theme == "dark"

        location = await manager.get_long_term_memory(user_id_ltm, "last_location")
        logger.info(f"LTM: User '{user_id_ltm}' location: {location}")
        assert location["city"] == "Testville"

        # Test LTM persistence (by creating a new manager instance that should load from file)
        logger.info("Creating new MemoryManager instance to test LTM persistence...")
        manager2 = MemoryManager(config=manager_config) # Same config, pointing to same LTM path
        await manager2.initialize()
        
        theme_reloaded = await manager2.get_long_term_memory(user_id_ltm, "preference_theme")
        logger.info(f"LTM (reloaded): User '{user_id_ltm}' theme: {theme_reloaded}")
        assert theme_reloaded == "dark"
        
        location_reloaded = await manager2.get_long_term_memory(user_id_ltm, "last_location")
        logger.info(f"LTM (reloaded): User '{user_id_ltm}' location: {location_reloaded}")
        assert location_reloaded["city"] == "Testville"


        # Test delete LTM
        deleted = await manager2.delete_long_term_memory(user_id_ltm, "preference_theme")
        assert deleted
        theme_after_delete = await manager2.get_long_term_memory(user_id_ltm, "preference_theme")
        logger.info(f"LTM: User '{user_id_ltm}' theme after delete: {theme_after_delete}")
        assert theme_after_delete is None
        
        # Test deleting non-existent key
        deleted_non_existent = await manager2.delete_long_term_memory(user_id_ltm, "non_existent_key")
        assert not deleted_non_existent

        # Test LTM for a different user (should be empty initially)
        user_id_ltm_other = "other_user_456"
        other_pref = await manager2.get_long_term_memory(user_id_ltm_other, "some_pref")
        assert other_pref is None
        logger.info(f"LTM: User '{user_id_ltm_other}' some_pref: {other_pref} (should be None)")


        # Test with no LTM path configured
        logger.info("\n--- Testing MemoryManager without LTM path ---")
        manager_no_ltm = MemoryManager(config={"default_max_history": 3})
        await manager_no_ltm.initialize()
        await manager_no_ltm.set_long_term_memory("user_noltm", "key", "value")
        val_noltm = await manager_no_ltm.get_long_term_memory("user_noltm", "key")
        assert val_noltm == "value" # Works in-memory cache
        # _save_user_ltm would have logged a warning and returned False, data not persisted.
        # To confirm, check that no file was created (if test_ltm_dir was specified for it)
        # This manager_no_ltm has self.long_term_storage_path = None

        # Clean up LTM test directory
        if os.path.exists(test_ltm_dir):
            for f_name in os.listdir(test_ltm_dir):
                os.remove(os.path.join(test_ltm_dir, f_name))
            os.rmdir(test_ltm_dir)
        logger.info(f"Cleaned up LTM test directory: {test_ltm_dir}")

    # asyncio.run(test_memory_manager()) # Commented out
    logger.info("MemoryManager example usage finished. Uncomment asyncio.run to test.")
