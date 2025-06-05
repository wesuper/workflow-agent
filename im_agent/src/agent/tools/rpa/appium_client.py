import asyncio
import logging
from typing import Any, Dict, List, Optional, Tuple

from appium.webdriver import Remote as AppiumRemote
from appium.options.common import AppiumOptions # Or platform-specific options like UiAutomator2Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException, WebDriverException

from .base import AbstractRPAClient, ElementLocator

logger = logging.getLogger(__name__)

# Mapping from our generic locator strategy to Appium's By strategy
APPIUM_BY_MAP = {
    "id": By.ID,
    "xpath": By.XPATH,
    "name": By.NAME, # Accessibility ID for Appium often
    "accessibility_id": By.ACCESSIBILITY_ID,
    "class_name": By.CLASS_NAME,
    "css_selector": By.CSS_SELECTOR, # For web contexts within apps
    "link_text": By.LINK_TEXT, # For web contexts
    "partial_link_text": By.PARTIAL_LINK_TEXT, # For web contexts
    "android_uiautomator": By.ANDROID_UIAUTOMATOR, # Android specific
    # Add iOS specific if needed: By.IOS_PREDICATE_STRING, By.IOS_CLASS_CHAIN
}


class AppiumRPAClient(AbstractRPAClient):
    """RPA client for Android and iOS using Appium."""

    def __init__(self):
        self.driver: Optional[AppiumRemote] = None
        self.config: Dict[str, Any] = {}

    async def initialize(self, config: Dict[str, Any]) -> bool:
        logger.info("Initializing AppiumRPAClient...")
        self.config = config
        server_url = self.config.get("appium_server_url")
        desired_capabilities = self.config.get("desired_capabilities")

        if not server_url or not desired_capabilities:
            logger.error("Appium server URL or desired capabilities not provided in config.")
            return False

        try:
            # For Appium 2.x, options objects are preferred over raw capabilities
            options = AppiumOptions()
            for key, value in desired_capabilities.items():
                options.set_capability(key, value)

            # Use asyncio.to_thread for the blocking AppiumRemote call
            self.driver = await asyncio.to_thread(
                AppiumRemote, command_executor=server_url, options=options
            )
            logger.info(f"Appium session initialized successfully. Session ID: {self.driver.session_id}")
            return True
        except WebDriverException as e:
            logger.error(f"Failed to connect to Appium server or start session: {e}", exc_info=True)
            self.driver = None
            return False
        except Exception as e: # Catch any other unexpected errors during init
            logger.error(f"An unexpected error occurred during Appium initialization: {e}", exc_info=True)
            self.driver = None
            return False


    async def shutdown(self) -> None:
        if self.driver:
            logger.info(f"Shutting down Appium session: {self.driver.session_id}")
            try:
                await asyncio.to_thread(self.driver.quit)
            except Exception as e:
                logger.error(f"Error during Appium driver quit: {e}", exc_info=True)
            finally:
                self.driver = None
        else:
            logger.info("Appium driver not initialized or already shut down.")

    async def _find_appium_element(self, locator: ElementLocator, timeout: int = 10) -> Optional[Any]:
        if not self.driver:
            logger.error("Appium driver not initialized.")
            return None

        by_strategy_str = locator.get("by", "id").lower()
        value = locator.get("value")

        if not value:
            logger.error(f"Locator 'value' not provided: {locator}")
            return None

        by_strategy = APPIUM_BY_MAP.get(by_strategy_str)
        if not by_strategy:
            logger.error(f"Unsupported locator strategy for Appium: {by_strategy_str}")
            return None

        try:
            element = await asyncio.to_thread(
                WebDriverWait(self.driver, timeout).until,
                EC.presence_of_element_located((by_strategy, value))
            )
            return element
        except TimeoutException:
            logger.warning(f"Timeout finding element with locator {locator} (strategy: {by_strategy}, value: '{value}')")
            return None
        except NoSuchElementException: # Should be caught by WebDriverWait, but as a fallback
            logger.warning(f"Element not found with locator {locator}")
            return None
        except Exception as e:
            logger.error(f"Error finding element {locator}: {e}", exc_info=True)
            return None

    async def find_element(self, locator: ElementLocator, timeout: int = 10) -> Optional[Any]:
        return await self._find_appium_element(locator, timeout)

    async def perform_click(self, locator: ElementLocator, timeout: int = 10) -> bool:
        element = await self._find_appium_element(locator, timeout)
        if element:
            try:
                # For click, also wait for clickable
                # Re-finding with clickable condition
                by_strategy_str = locator.get("by", "id").lower()
                value = locator.get("value")
                by_strategy = APPIUM_BY_MAP.get(by_strategy_str)

                clickable_element = await asyncio.to_thread(
                    WebDriverWait(self.driver, timeout).until,
                    EC.element_to_be_clickable((by_strategy, value)) # type: ignore
                )
                await asyncio.to_thread(clickable_element.click)
                logger.info(f"Clicked element: {locator}")
                return True
            except TimeoutException:
                logger.error(f"Timeout: Element {locator} not clickable within {timeout}s.")
                return False
            except Exception as e:
                logger.error(f"Error clicking element {locator}: {e}", exc_info=True)
                return False
        return False

    async def send_keys(self, locator: ElementLocator, text: str, timeout: int = 10) -> bool:
        element = await self._find_appium_element(locator, timeout)
        if element:
            try:
                await asyncio.to_thread(element.send_keys, text)
                logger.info(f"Sent keys '{text}' to element: {locator}")
                return True
            except Exception as e:
                logger.error(f"Error sending keys to element {locator}: {e}", exc_info=True)
                return False
        return False

    async def get_text(self, locator: ElementLocator, timeout: int = 10) -> Optional[str]:
        element = await self._find_appium_element(locator, timeout)
        if element:
            try:
                return await asyncio.to_thread(getattr, element, 'text')
            except Exception as e:
                logger.error(f"Error getting text from element {locator}: {e}", exc_info=True)
                return None
        return None

    async def element_exists(self, locator: ElementLocator, timeout: int = 5) -> bool:
        element = await self._find_appium_element(locator, timeout)
        return element is not None

    async def capture_screenshot(self, save_path: str) -> bool:
        if not self.driver:
            logger.error("Appium driver not initialized.")
            return False
        try:
            success = await asyncio.to_thread(self.driver.get_screenshot_as_file, save_path)
            if success:
                logger.info(f"Screenshot saved to {save_path}")
            else:
                logger.error(f"Appium driver failed to save screenshot to {save_path}")
            return success
        except Exception as e:
            logger.error(f"Error capturing screenshot: {e}", exc_info=True)
            return False

    async def scroll(self, direction: str, locator: Optional[ElementLocator] = None, distance_percentage: float = 0.5) -> bool:
        if not self.driver:
            logger.error("Appium driver not initialized.")
            return False
        try:
            # Simplified scroll using swipe (common for mobile)
            # More sophisticated scrolling might use W3C Actions or UIAutomator specific commands
            window_size = await asyncio.to_thread(self.driver.get_window_size)
            width, height = window_size['width'], window_size['height']

            start_x, start_y, end_x, end_y = 0, 0, 0, 0
            scroll_distance = int(height * distance_percentage)

            if direction.lower() == "down":
                start_x = width // 2
                start_y = int(height * 0.8) # Start swipe from lower part of screen
                end_x = width // 2
                end_y = start_y - scroll_distance
            elif direction.lower() == "up":
                start_x = width // 2
                start_y = int(height * 0.2) # Start swipe from upper part of screen
                end_x = width // 2
                end_y = start_y + scroll_distance
            elif direction.lower() == "left": # Swipe right-to-left to scroll content left
                start_y = height // 2
                start_x = int(width * 0.8)
                end_y = height // 2
                end_x = start_x - int(width * distance_percentage)
            elif direction.lower() == "right": # Swipe left-to-right to scroll content right
                start_y = height // 2
                start_x = int(width * 0.2)
                end_y = height // 2
                end_x = start_x + int(width * distance_percentage)
            else:
                logger.error(f"Unsupported scroll direction: {direction}")
                return False

            # Ensure coordinates are within bounds
            end_y = max(0, min(height -1 , end_y))
            end_x = max(0, min(width -1, end_x))

            logger.info(f"Scrolling {direction}: from ({start_x},{start_y}) to ({end_x},{end_y})")
            await asyncio.to_thread(self.driver.swipe, start_x, start_y, end_x, end_y, duration=800) # duration in ms
            return True
        except Exception as e:
            logger.error(f"Error during scroll: {e}", exc_info=True)
            return False

    async def launch_app(self, app_id_or_name: str) -> bool:
        if not self.driver:
            logger.error("Appium driver not initialized.")
            return False
        try:
            # For Android, app_id_or_name is typically package name. For iOS, bundle ID.
            await asyncio.to_thread(self.driver.activate_app, app_id_or_name)
            logger.info(f"Launched/Activated app: {app_id_or_name}")
            return True
        except Exception as e:
            logger.error(f"Error launching app {app_id_or_name}: {e}", exc_info=True)
            return False

    async def close_app(self, app_id_or_name: str) -> bool:
        if not self.driver:
            logger.error("Appium driver not initialized.")
            return False
        try:
            await asyncio.to_thread(self.driver.terminate_app, app_id_or_name)
            logger.info(f"Terminated app: {app_id_or_name}")
            return True
        except Exception as e:
            logger.error(f"Error terminating app {app_id_or_name}: {e}", exc_info=True)
            return False

    async def execute_workflow(self, workflow_id: str, params: Optional[Dict[str, Any]] = None) -> Tuple[bool, str]:
        logger.warning("Method execute_workflow not yet implemented for AppiumRPAClient. "
                       "Consider using direct RPA methods or custom Python Appium scripts "
                       "called by a general script execution tool if complex pre-defined Appium sequences are needed.")
        return False, "Not implemented for AppiumRPAClient"
