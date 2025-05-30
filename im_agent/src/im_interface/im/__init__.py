import asyncio
import logging
from typing import Any, Callable, Dict, List
import os # Added for __main__ block

# Adjusted import path for AppSettings
from agent.config import AppSettings 
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
    on_message_callback: Callable[[Dict[str, Any]], Any] 
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
    im_settings_all = app_settings.get_im_settings() 

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
    logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    
    class MockAppSettings:
        def __init__(self, settings_dict: Dict[str, Any]):
            self.settings = settings_dict
        def get_config(self, key: str, default: Any = None) -> Any:
            return self.settings.get(key, default)
        def get_im_settings(self) -> Dict[str, Any]:
            return self.settings.get("im_settings", {})

    async def mock_message_processor(message: Dict[str, Any]):
        logger.info(f"GLOBAL_MESSAGE_PROCESSOR received: {message}")
        await asyncio.sleep(0.01)

    async def run_factory_tests():
        print("\n--- Scenario 1: Dummy Adapter Enabled ---")
        settings_v1 = {
            "im_settings": {
                "dummy": {"enabled": True, "simulated_message_interval_seconds": 3},
                "wechat_work": {"enabled": False}, "discord": {"enabled": False}
            }
        }
        mock_app_settings_v1 = MockAppSettings(settings_v1)
        adapters_v1 = await get_im_adapters(mock_app_settings_v1, mock_message_processor)
        assert len(adapters_v1) == 1
        assert isinstance(adapters_v1[0], DummyIMAdapter)
        print(f"Adapters loaded: {[type(a).__name__ for a in adapters_v1]}")
        dummy_adapter_instance = next((a for a in adapters_v1 if isinstance(a, DummyIMAdapter)), None)
        if dummy_adapter_instance:
            if await dummy_adapter_instance.connect():
                listen_task = asyncio.create_task(dummy_adapter_instance.start_listening())
                await asyncio.sleep(settings_v1["im_settings"]["dummy"]["simulated_message_interval_seconds"] + 0.5)
                await dummy_adapter_instance.disconnect()
                listen_task.cancel()
                try: await listen_task
                except asyncio.CancelledError: pass
        
        print("\n--- Scenario 2: Multiple Adapters (Dummy and Discord enabled) ---")
        os.environ["TEST_DISCORD_TOKEN_FOR_FACTORY"] = "fake_discord_token"
        settings_v2 = {
            "im_settings": {
                "dummy": {"enabled": True, "simulated_message_interval_seconds": 5},
                "wechat_work": {"enabled": True, "corp_id": "test_corp", "agent_id": "test_agent", "secret_env_var": "FAKE_WECHAT_SECRET"},
                "discord": {"enabled": True, "bot_token_env_var": "TEST_DISCORD_TOKEN_FOR_FACTORY"},
                "unsupported_platform": {"enabled": True}
            }
        }
        mock_app_settings_v2 = MockAppSettings(settings_v2)
        adapters_v2 = await get_im_adapters(mock_app_settings_v2, mock_message_processor)
        assert len(adapters_v2) == 3
        adapter_names_v2 = sorted([type(a).__name__ for a in adapters_v2])
        print(f"Adapters loaded: {adapter_names_v2}")
        assert "DummyIMAdapter" in adapter_names_v2
        assert "WeChatWorkAdapter" in adapter_names_v2
        assert "DiscordAdapter" in adapter_names_v2
        del os.environ["TEST_DISCORD_TOKEN_FOR_FACTORY"]

    try:
        asyncio.run(run_factory_tests())
    except KeyboardInterrupt: logger.info("IM Factory test interrupted by user.")
    logger.info("IM Adapter Factory example usage (from im_interface.im) finished.")
