from abc import ABC, abstractmethod
from typing import Any, Dict, List, Tuple, Optional

ElementLocator = Dict[str, str] # Example: {"by": "id", "value": "some_id"}

class AbstractRPAClient(ABC):
    """Abstract interface for Robotic Process Automation clients."""

    @abstractmethod
    async def initialize(self, config: Dict[str, Any]) -> bool:
        """
        Initializes the RPA client with platform-specific configurations.
        Returns True on success, False otherwise.
        """
        pass

    @abstractmethod
    async def shutdown(self) -> None:
        """Cleans up resources, disconnects sessions, etc."""
        pass

    @abstractmethod
    async def perform_click(self, locator: ElementLocator, timeout: int = 10) -> bool:
        """
        Clicks an element identified by the locator.
        Returns True if successful, False otherwise.
        """
        pass

    @abstractmethod
    async def send_keys(self, locator: ElementLocator, text: str, timeout: int = 10) -> bool:
        """
        Types text into an element identified by the locator.
        Returns True if successful, False otherwise.
        """
        pass

    @abstractmethod
    async def find_element(self, locator: ElementLocator, timeout: int = 10) -> Optional[Any]:
        """
        Finds a UI element based on the locator.
        Returns a platform-specific element object or None if not found/error.
        This element object might be used by other more specific RPA methods if needed.
        """
        pass
            
    @abstractmethod
    async def get_text(self, locator: ElementLocator, timeout: int = 10) -> Optional[str]:
        """
        Gets the text content of an element.
        Returns the text string or None if not found/error.
        """
        pass

    @abstractmethod
    async def element_exists(self, locator: ElementLocator, timeout: int = 5) -> bool:
        """Checks if an element exists on the screen and is interactable."""
        pass

    @abstractmethod
    async def capture_screenshot(self, save_path: str) -> bool:
        """
        Takes a screenshot and saves it to the given path.
        Returns True if successful, False otherwise.
        """
        pass

    @abstractmethod
    async def execute_workflow(self, workflow_id: str, params: Optional[Dict[str, Any]] = None) -> Tuple[bool, str]:
        """
        Executes a pre-defined, platform-specific workflow or script.
        'workflow_id' refers to an identifier in a config map (e.g., rpa_scripts.json).
        'params' are parameters to be passed to the workflow.
        Returns a tuple: (success: bool, output_message: str).
        """
        pass
    
    @abstractmethod
    async def scroll(self, direction: str, locator: Optional[ElementLocator] = None, distance_percentage: float = 0.5) -> bool:
        """Scrolls the screen or a specific scrollable element."""
        pass

    @abstractmethod
    async def launch_app(self, app_id_or_name: str) -> bool:
        """Launches an application."""
        pass

    @abstractmethod
    async def close_app(self, app_id_or_name: str) -> bool:
        """Closes an application."""
        pass
