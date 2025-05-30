import asyncio
import logging
from typing import Any, Callable, Dict, List

from ..config import AppSettings # Assuming AppSettings is in agent.config
from .base import IMInterface
from .dummy_im import DummyIMAdapter
from .wechat_work_adapter import WeChatWorkAdapter
from .discord_adapter import DiscordAdapter

logger = logging.getLogger(__name__)

SUPPORTED_IM_PLATFORMS: Dict[str, type[IMInterface]] = {
    "dummy": DummyIMAdapter,
    "wechat_work": WeChatWorkAdapter,
    "discord": DiscordAdapter,
    # Future IM platform adapters can be added here
}

async def get_im_adapters(
    app_settings: AppSettings, 
    on_message_callback: Callable[[Dict[str, Any]], Any] # Allow async callback (Any covers Awaitable)
) -> List[IMInterface]:
    """
    Factory function to get and initialize all enabled IM adapters based on application settings.

    Args:
        app_settings: The application settings object.
        on_message_callback: Async callback function to be invoked when a message is received
                             from any of the IM platforms.

    Returns:
        A list of initialized IMInterface instances.
    """
    adapters: List[IMInterface] = []
    im_settings_all = app_settings.get_im_settings() # This should return the whole "im_settings" dict

    if not im_settings_all:
        logger.warning("No 'im_settings' found in application configuration. No IM adapters will be loaded.")
        return adapters

    for platform_name, platform_config in im_settings_all.items():
        if not isinstance(platform_config, dict):
            logger.warning(f"Configuration for IM platform '{platform_name}' is not a valid dictionary. Skipping.")
            continue

        if platform_config.get("enabled", False):
            if platform_name in SUPPORTED_IM_PLATFORMS:
                adapter_class = SUPPORTED_IM_PLATFORMS[platform_name]
                try:
                    adapter_instance = adapter_class(
                        platform_name=platform_name,
                        config=platform_config,
                        on_message_callback=on_message_callback
                    )
                    # Attempt to connect each adapter upon initialization by the factory
                    # If connect fails, it will be logged by the adapter, but we might still add it to the list
                    # or decide to exclude it. For now, let's add it and let reconnections be handled later if needed.
                    # if await adapter_instance.connect():
                    #    logger.info(f"Successfully connected and initialized IM adapter for '{platform_name}'.")
                    #    adapters.append(adapter_instance)
                    # else:
                    #    logger.error(f"Failed to connect IM adapter for '{platform_name}'. It will not be added.")
                    
                    # Simpler: Initialize and add. Connection is a separate step managed by the main agent loop.
                    adapters.append(adapter_instance)
                    logger.info(f"Initialized IM adapter for '{platform_name}'. Connection will be managed by the main agent process.")

                except Exception as e:
                    logger.error(f"Error initializing IM adapter for {platform_name}: {e}", exc_info=True)
            else:
                logger.warning(f"Unsupported IM platform configured: '{platform_name}'. Skipping.")
        else:
            logger.info(f"IM platform '{platform_name}' is disabled in configuration. Skipping.")
            
    return adapters

if __name__ == '__main__':
    # Example Usage
    logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    
    # --- Mock AppSettings for testing ---
    class MockAppSettings:
        def __init__(self, settings_dict: Dict[str, Any]):
            self.settings = settings_dict

        def get_config(self, key: str, default: Any = None) -> Any:
            return self.settings.get(key, default)

        def get_im_settings(self) -> Dict[str, Any]:
            return self.settings.get("im_settings", {})

    async def mock_message_processor(message: Dict[str, Any]):
        logger.info(f"GLOBAL_MESSAGE_PROCESSOR received: {message}")
        # Simulate some async work
        await asyncio.sleep(0.01)

    # --- Test Scenarios ---
    async def run_factory_tests():
        # Scenario 1: Dummy adapter enabled
        print("\n--- Scenario 1: Dummy Adapter Enabled ---")
        settings_v1 = {
            "im_settings": {
                "dummy": {
                    "enabled": True,
                    "simulated_message_interval_seconds": 3 # Quick for test
                },
                "wechat_work": {"enabled": False},
                "discord": {"enabled": False}
            }
        }
        mock_app_settings_v1 = MockAppSettings(settings_v1)
        adapters_v1 = await get_im_adapters(mock_app_settings_v1, mock_message_processor)
        assert len(adapters_v1) == 1
        assert isinstance(adapters_v1[0], DummyIMAdapter)
        print(f"Adapters loaded: {[type(a).__name__ for a in adapters_v1]}")
        
        # Test connect and a bit of listening for the dummy
        dummy_adapter_instance = next((a for a in adapters_v1 if isinstance(a, DummyIMAdapter)), None)
        if dummy_adapter_instance:
            if await dummy_adapter_instance.connect():
                listen_task = asyncio.create_task(dummy_adapter_instance.start_listening())
                await asyncio.sleep(settings_v1["im_settings"]["dummy"]["simulated_message_interval_seconds"] + 0.5) # Wait for one message
                await dummy_adapter_instance.disconnect() # This will cancel the listen_task
                listen_task.cancel() # Ensure cancellation if disconnect doesn't handle it fully
                try:
                    await listen_task
                except asyncio.CancelledError:
                    pass # Expected
            else:
                print("Failed to connect dummy adapter in test")


        # Scenario 2: Multiple adapters, some enabled, some not
        print("\n--- Scenario 2: Multiple Adapters (Dummy and Discord enabled) ---")
        # Simulate Discord bot token env var
        import os
        os.environ["TEST_DISCORD_TOKEN_FOR_FACTORY"] = "fake_discord_token"
        settings_v2 = {
            "im_settings": {
                "dummy": {"enabled": True, "simulated_message_interval_seconds": 5},
                "wechat_work": {
                    "enabled": True, # Will log placeholder status
                    "corp_id": "test_corp", "agent_id": "test_agent", "secret_env_var": "FAKE_WECHAT_SECRET"
                },
                "discord": {
                    "enabled": True, # Will log placeholder status
                    "bot_token_env_var": "TEST_DISCORD_TOKEN_FOR_FACTORY"
                },
                "unsupported_platform": {"enabled": True} # Should be skipped
            }
        }
        mock_app_settings_v2 = MockAppSettings(settings_v2)
        adapters_v2 = await get_im_adapters(mock_app_settings_v2, mock_message_processor)
        assert len(adapters_v2) == 3 # Dummy, WeChatWork, Discord
        adapter_names_v2 = sorted([type(a).__name__ for a in adapters_v2])
        print(f"Adapters loaded: {adapter_names_v2}")
        assert "DummyIMAdapter" in adapter_names_v2
        assert "WeChatWorkAdapter" in adapter_names_v2
        assert "DiscordAdapter" in adapter_names_v2
        del os.environ["TEST_DISCORD_TOKEN_FOR_FACTORY"]


        # Scenario 3: No IM settings
        print("\n--- Scenario 3: No IM Settings ---")
        settings_v3 = {} # No "im_settings" key
        mock_app_settings_v3 = MockAppSettings(settings_v3)
        adapters_v3 = await get_im_adapters(mock_app_settings_v3, mock_message_processor)
        assert len(adapters_v3) == 0
        print(f"Adapters loaded: {len(adapters_v3)}")

        # Scenario 4: IM settings present but empty
        print("\n--- Scenario 4: Empty IM Settings ---")
        settings_v4 = {"im_settings": {}}
        mock_app_settings_v4 = MockAppSettings(settings_v4)
        adapters_v4 = await get_im_adapters(mock_app_settings_v4, mock_message_processor)
        assert len(adapters_v4) == 0
        print(f"Adapters loaded: {len(adapters_v4)}")
        
        # Scenario 5: IM platform config is not a dict
        print("\n--- Scenario 5: Invalid platform config (not a dict) ---")
        settings_v5 = {"im_settings": {"dummy": "this_should_be_a_dict"}}
        mock_app_settings_v5 = MockAppSettings(settings_v5)
        adapters_v5 = await get_im_adapters(mock_app_settings_v5, mock_message_processor)
        assert len(adapters_v5) == 0
        print(f"Adapters loaded: {len(adapters_v5)}")


        print("\nIM Adapter Factory tests finished.")

    try:
        asyncio.run(run_factory_tests())
    except KeyboardInterrupt:
        logger.info("IM Factory test interrupted by user.")

    logger.info("IM Adapter Factory example usage finished.")
