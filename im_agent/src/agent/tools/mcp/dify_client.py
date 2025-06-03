import logging
import os
from typing import Any, Dict, List, Tuple, Optional # Added Optional
import httpx # For async HTTP requests

from .base import AbstractMCPClient

logger = logging.getLogger(__name__)

class DifyClient(AbstractMCPClient):
    def __init__(self):
        self.api_key: Optional[str] = None
        self.api_base_url: Optional[str] = None
        self.configured_apps: Dict[str, Dict[str, Any]] = {} # Stores Dify app specific info
        self.client: Optional[httpx.AsyncClient] = None
        logger.info("DifyClient instance created. Needs initialization.")

    async def initialize(self, config: Dict[str, Any]) -> bool:
        """
        Initializes the Dify client.
        Config should include: 'api_key_env_var', 'api_base_url',
                             'apps': [{"name": "my_chat_app", "app_id": "...", "description": "...", "features": ["chat", "completion"]}]
        """
        logger.info("Initializing DifyClient...")
        api_key_env_var = config.get("api_key_env_var")
        if not api_key_env_var:
            logger.error("Dify config missing 'api_key_env_var'.")
            return False

        self.api_key = os.environ.get(api_key_env_var)
        self.api_base_url = config.get("api_base_url", "https://api.dify.ai/v1")

        if not self.api_key:
            logger.error(f"Dify API key not found in environment variable '{api_key_env_var}'.")
            return False

        raw_apps = config.get("apps", [])
        if not isinstance(raw_apps, list):
            logger.error("Dify config 'apps' must be a list.")
            return False

        for app_config in raw_apps:
            if isinstance(app_config, dict) and "name" in app_config:
                self.configured_apps[app_config['name']] = app_config
            else:
                logger.warning(f"Skipping invalid Dify app configuration: {app_config}")

        self.client = httpx.AsyncClient(base_url=self.api_base_url, headers={
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        })

        logger.info(f"DifyClient initialized. Base URL: {self.api_base_url}, Apps: {list(self.configured_apps.keys())}")
        return True

    async def invoke_service(self, service_name: str, parameters: Dict[str, Any]) -> Tuple[bool, Dict[str, Any]]:
        """
        Invokes a Dify application (service_name should map to a configured Dify app name).
        Parameters should match Dify app's requirements (e.g., query, user, conversation_id).
        """
        if not self.client:
            logger.error("DifyClient not initialized or initialization failed.")
            return False, {"error": "DifyClient not initialized."}

        dify_app_config = self.configured_apps.get(service_name)
        if not dify_app_config:
            return False, {"error": f"Dify app '{service_name}' not configured for this client."}

        query = parameters.get("query")
        user_id = parameters.get("user_id", "default-dify-user") # Dify requires a user ID

        if not query:
            return False, {"error": "Missing 'query' in parameters for Dify app."}

        # Determine endpoint and payload based on Dify app features/type
        # This is a simplified example. Dify's API for different app types (chat, completion, workflow) varies.
        # Consult Dify documentation for the correct endpoint and payload structure.
        # Example: /chat-messages for chat apps, /completion-messages for completion apps, etc.

        endpoint = ""
        data_payload: Dict[str, Any] = {}
        app_features = dify_app_config.get("features", [])

        # This logic is highly dependent on Dify's API and how you structure your app configs
        if "chat" in app_features: # Assuming a chat-type application
            endpoint = "/chat-messages"
            data_payload = {
                "inputs": parameters.get("inputs", {}), # Custom inputs for the Dify app
                "query": query,
                "user": user_id,
                "response_mode": "streaming" if parameters.get("streaming", False) else "blocking", # Example
            }
            if "conversation_id" in parameters:
                data_payload["conversation_id"] = parameters["conversation_id"]
        elif "completion" in app_features: # Assuming a completion-type application
            endpoint = "/completion-messages" # Or similar, check Dify docs
            data_payload = {
                "inputs": parameters.get("inputs", {}),
                "prompt": query, # 'prompt' might be used instead of 'query' for some Dify apps
                "user": user_id,
            }
        # Add handling for "workflow" apps if needed, e.g., /workflows/{app_id}/run
        # elif "workflow" in app_features and "app_id" in dify_app_config:
        #     endpoint = f"/workflows/{dify_app_config['app_id']}/run"
        #     data_payload = {"inputs": parameters.get("inputs", {}), "user": user_id}


        if not endpoint:
            logger.error(f"Could not determine Dify endpoint for app '{service_name}' with features: {app_features}")
            return False, {"error": f"Unsupported Dify app type or features for '{service_name}'."}

        logger.info(f"Invoking Dify app '{service_name}' at endpoint '{endpoint}' with payload: {data_payload}")

        try:
            response = await self.client.post(endpoint, json=data_payload, timeout=self.config.get("timeout_seconds", 30))
            response.raise_for_status()
            return True, response.json()
        except httpx.HTTPStatusError as e:
            logger.error(f"Dify API HTTPStatusError for '{service_name}': {e.response.status_code} - {e.response.text}", exc_info=True)
            return False, {"error": "Dify API request failed.", "status_code": e.response.status_code, "details": e.response.text}
        except httpx.RequestError as e: # Catches network errors, timeouts handled by httpx client config
            logger.error(f"Dify API RequestError for '{service_name}': {e}", exc_info=True)
            return False, {"error": f"Dify API request failed due to network issue: {str(e)}"}
        except Exception as e:
            logger.error(f"Unexpected error invoking Dify app '{service_name}': {e}", exc_info=True)
            return False, {"error": f"An unexpected error occurred with Dify: {str(e)}"}

    async def add_service(self, service_config: Dict[str, Any], user_id: str) -> bool:
        # This method could allow dynamic client-side registration of a Dify app,
        # if the DifyClient's configuration structure supports it (e.g., by adding to self.configured_apps).
        # For now, it's more common to configure Dify apps at startup via the main config.
        app_name = service_config.get("name")
        if not app_name:
            logger.warning("Dify service config must include a 'name' to be added.")
            return False

        # Basic validation, more might be needed depending on Dify app requirements
        if "app_id" not in service_config or "features" not in service_config:
            logger.warning(f"Dify service config for '{app_name}' is missing 'app_id' or 'features'.")
            return False

        self.configured_apps[app_name] = service_config
        logger.info(f"Dify app '{app_name}' added/updated in client configuration by user '{user_id}'.")
        # Note: This doesn't persist the Dify app config anywhere beyond this client instance's memory.
        return True

    async def list_services(self) -> List[Dict[str, Any]]:
        """Lists Dify apps configured for this client."""
        return list(self.configured_apps.values())

    async def shutdown(self): # Ensure AbstractRPAClient method is implemented
        if self.client:
            logger.info("Shutting down DifyClient's HTTPX session.")
            await self.client.aclose()
            self.client = None
        logger.info("DifyClient shutdown.")

if __name__ == '__main__':
    import asyncio
    logging.basicConfig(level=logging.DEBUG)

    async def test_dify_client():
        logger.info("--- Testing DifyClient ---")

        # Mock configuration - Set DIFY_TEST_KEY environment variable for this to run
        os.environ["DIFY_TEST_KEY"] = "your_actual_dify_api_key_or_dummy"

        dify_config = {
            "api_key_env_var": "DIFY_TEST_KEY",
            "api_base_url": "https://api.dify.ai/v1", # Use your actual Dify API base if self-hosting
            "apps": [
                {
                    "name": "general_chat_app",
                    "app_id": "YOUR_DIFY_CHAT_APP_ID", # Replace with actual Dify App ID
                    "description": "General Chat with Dify",
                    "features": ["chat"] # Indicates it's a chat-type application
                },
                {
                    "name": "story_writer_app",
                    "app_id": "YOUR_DIFY_COMPLETION_APP_ID", # Replace with actual Dify App ID
                    "description": "Story Writer with Dify",
                    "features": ["completion"] # Indicates it's a completion-type application
                }
            ]
        }

        if os.environ["DIFY_TEST_KEY"] == "your_actual_dify_api_key_or_dummy" or \
           dify_config["apps"][0]["app_id"] == "YOUR_DIFY_CHAT_APP_ID":
            logger.warning("Using placeholder API key or App ID for Dify test. Actual API calls will likely fail.")

        dify_client = DifyClient()
        init_success = await dify_client.initialize(dify_config)
        print(f"DifyClient Init success: {init_success}")

        if not init_success:
            logger.error("DifyClient initialization failed. Aborting further tests.")
            await dify_client.shutdown()
            return

        # List services
        services = await dify_client.list_services()
        print(f"Available Dify services/apps: {services}")
        assert len(services) == 2

        # Test invoking a "chat" type app
        print("\n--- Invoking Dify Chat App ---")
        chat_params = {
            "query": "Hello Dify, how are you?",
            "user_id": "test_user_123",
            # "conversation_id": "conv_abc_123" # Optional
            "inputs": {} # Optional, if your Dify app uses specific input variables
        }
        success, response = await dify_client.invoke_service("general_chat_app", chat_params)
        print(f"Chat App - Success: {success}, Response: {response}")
        # Add assertions based on expected Dify response structure or dummy key failure

        # Test invoking a "completion" type app
        print("\n--- Invoking Dify Completion App ---")
        completion_params = {
            "query": "Write a short story about a robot.", # 'query' will be mapped to 'prompt'
            "user_id": "test_user_456",
            "inputs": {"style": "funny"} # Example custom input
        }
        success, response = await dify_client.invoke_service("story_writer_app", completion_params)
        print(f"Completion App - Success: {success}, Response: {response}")

        await dify_client.shutdown()
        del os.environ["DIFY_TEST_KEY"] # Clean up

    # asyncio.run(test_dify_client()) # Commented out
    print("\nDifyClient example usage finished. Uncomment to run (requires DIFY_TEST_KEY and app IDs).")
