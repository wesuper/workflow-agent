from abc import ABC, abstractmethod
from typing import Any, Dict, List

class MCPInterface(ABC):
    @abstractmethod
    def initialize(self, app_settings: Any): # app_settings is of type AppSettings from agent.config
        """
        Initializes the MCP handler with application settings.
        This method is for loading initial configurations and setting up the handler.
        """
        pass

    @abstractmethod
    def invoke_service(self, service_name: str, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """
        Invokes a registered MCP service.

        Args:
            service_name: The name of the service to invoke.
            parameters: A dictionary of parameters to pass to the service.

        Returns:
            A dictionary containing the service's response.
        """
        pass

    @abstractmethod
    def add_service(self, service_config: Dict[str, Any], user_id: str) -> bool:
        """
        Dynamically adds a new MCP service.

        Args:
            service_config: The configuration dictionary for the new service.
                            Example: {"name": "MyCustomAPI", "url": "https://api.example.com/invoke", "method": "POST", ...}
            user_id: The ID of the user attempting to add the service (for whitelist check).

        Returns:
            True if the service was added successfully, False otherwise.
        """
        pass

    @abstractmethod
    def list_services(self) -> List[str]:
        """
        Lists the names of all currently available MCP services.

        Returns:
            A list of service names.
        """
        pass
