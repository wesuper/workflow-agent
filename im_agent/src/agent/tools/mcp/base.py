from abc import ABC, abstractmethod
from typing import Any, Dict, List, Tuple

class AbstractMCPClient(ABC):
    """Abstract interface for Master Control Program (MCP) clients."""

    @abstractmethod
    async def initialize(self, config: Dict[str, Any]) -> bool:
        """
        Initializes the MCP client, potentially loading service definitions.
        'config' might contain path to mcp-servers.json or specific service configs.
        Returns True on success.
        """
        pass

    @abstractmethod
    async def invoke_service(self, service_name: str, parameters: Dict[str, Any]) -> Tuple[bool, Dict[str, Any]]:
        """
        Invokes a registered MCP service.
        Returns a tuple: (success: bool, result_dict: Dict[str, Any]).
        The result_dict should contain the service's response or an error message.
        """
        pass

    @abstractmethod
    async def add_service(self, service_config: Dict[str, Any], user_id: str) -> bool:
        """
        Dynamically adds a new MCP service configuration.
        Requires user_id for whitelist verification.
        Returns True if the service was added successfully, False otherwise.
        """
        pass

    @abstractmethod
    async def list_services(self) -> List[Dict[str, Any]]:
        """
        Lists available MCP services with their definitions/schemas.
        Returns a list of service definition dictionaries.
        """
        pass
