from fastapi import FastAPI, Request, HTTPException # Added Request, HTTPException
from pydantic import BaseModel
import logging
import datetime
import asyncio
from typing import List, Optional, Any, Dict # Added List, Optional, Any, Dict

# Assuming AgentState and AppSettings are correctly placed and importable
# This might need adjustment depending on final project structure and PYTHONPATH
from ..core.state import AgentState
# AppSettings will be accessed via request.app.state.app_settings

logger = logging.getLogger(__name__)
if not logger.hasHandlers():
    logging.basicConfig(level=logging.INFO)

app = FastAPI(
    title="IM-Agent API",
    description="API for interacting with the IM-Agent and monitoring its events.",
    version="0.1.0"
)

# --- Existing ChatMessage and ChatResponse Models ---
class ChatMessage(BaseModel):
    user_id: str
    chat_id: str
    message: str
    platform: str = "frontend_rest"

class ChatResponse(BaseModel):
    reply: str
    chat_id: str
    timestamp: datetime.datetime

# --- New Config Endpoint Models ---
class FrontendConfigResponse(BaseModel):
    llm_providers_available: List[str] # e.g. ["OpenAI", "DummyLLM"] from LLMFactory.SUPPORTED_LLM_PROVIDERS
    default_llm_provider: Optional[str] # From AppSettings.llm_provider
    rpa_platforms_configured: List[str] # e.g. ["macos", "android"] if configs exist
    mcp_service_count: int # Count of general MCP services from MCPServiceHandler
    dify_apps_configured: List[str] # Names of configured Dify apps

class UpdateConfigRequest(BaseModel):
    config_key_path: str # e.g., "llm_config.model_name" or "im_settings.discord.enabled"
    new_value: Any

# --- Existing Chat Endpoint ---
@app.post("/api/v1/chat", response_model=ChatResponse)
async def handle_chat_message(message: ChatMessage, fastapi_request: Request):
    logger.info(f"Received message via REST API from user '{message.user_id}' in chat '{message.chat_id}' on platform '{message.platform}': {message.message}")

    langgraph_app = getattr(fastapi_request.app.state, "langgraph_app", None)
    if not langgraph_app:
        logger.error("LangGraph app not found in FastAPI app state. Cannot process message.")
        raise HTTPException(status_code=503, detail="Agent processing backend is not available.")

    simulated_raw_im_message = {
        "message": message.message,
        "platform": message.platform,
        "chat_id": message.chat_id,
        "user_id": message.user_id,
        "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "message_id": f"rest_{datetime.datetime.now(datetime.timezone.utc).timestamp()}"
    }
    initial_graph_state: AgentState = {
        "raw_im_message": simulated_raw_im_message,
        "conversation_history": [],
    }

    agent_reply = "Error: Could not get a response from the agent."
    try:
        config = {"configurable": {"thread_id": message.chat_id}}
        logger.debug(f"Invoking LangGraph app for chat_id '{message.chat_id}' via REST API...")
        final_state = await langgraph_app.ainvoke(initial_graph_state, config=config)
        logger.debug(f"LangGraph app invocation complete for chat_id '{message.chat_id}'.")

        response_to_user = final_state.get("final_response_to_user")
        error_to_user = final_state.get("error_message_to_user")

        if error_to_user: agent_reply = error_to_user
        elif response_to_user: agent_reply = response_to_user
        else: agent_reply = "Agent processed the message but provided no specific reply."
    except Exception as e:
        logger.error(f"Error invoking LangGraph app via REST API for chat_id '{message.chat_id}': {e}", exc_info=True)
        agent_reply = "Sorry, a critical error occurred while processing your request via REST API."
        raise HTTPException(status_code=500, detail=agent_reply)

    return ChatResponse(
        reply=agent_reply,
        chat_id=message.chat_id,
        timestamp=datetime.datetime.now(datetime.timezone.utc)
    )

# --- New Config Endpoints ---
@app.get("/api/v1/config", response_model=FrontendConfigResponse)
async def get_frontend_config(request: Request):
    logger.info("GET /api/v1/config called")
    app_settings = getattr(request.app.state, "app_settings", None)
    # Also get other initialized components if needed for counts
    mcp_client = getattr(request.app.state, "mcp_client", None) # General MCP client
    # dify_clients_map = getattr(request.app.state, "dify_clients_map", {}) # If multiple Dify clients

    if not app_settings:
        logger.error("AppSettings not found in application state for GET /api/v1/config.")
        raise HTTPException(status_code=500, detail="Server configuration error: AppSettings not initialized.")

    # LLM Info
    # LLMFactory.SUPPORTED_LLM_PROVIDERS is defined in tools.llm.factory
    # To access it here without direct import, it could be stored on app_settings or app.state during startup
    # For now, let's assume AppSettings can provide this if needed, or we hardcode based on knowns.
    # A better way: main.py populates app.state.supported_llm_providers from LLMFactory.
    # For this task, let's assume AppSettings has a way to list them or we use a placeholder.

    # Placeholder for available LLM providers (ideally from LLMFactory.SUPPORTED_LLM_PROVIDERS.keys())
    # This requires LLMFactory to be accessible or its list stored in app_settings/app.state
    # For now, try to get from app_settings if it was populated there.
    llm_providers_available = app_settings.get_config("available_llm_providers_for_frontend", ["OpenAI", "DummyLLM"])
    default_llm_provider = app_settings.get_config("llm_provider")

    # RPA Info
    rpa_platforms_configured = []
    rpa_platform_configs = app_settings.get_config("rpa_platforms_config", {})
    if isinstance(rpa_platform_configs, dict):
        rpa_platforms_configured = [platform for platform, config in rpa_platform_configs.items() if config and config.get("enabled", True)]

    # MCP Info (General MCPServiceHandler)
    mcp_service_count = 0
    if mcp_client and hasattr(mcp_client, 'list_services'):
        try:
            # list_services might be async, ensure it's awaited if so.
            # The current AbstractMCPClient.list_services is async.
            # This endpoint is async, so we can await.
            mcp_services_list = await mcp_client.list_services()
            mcp_service_count = len(mcp_services_list)
        except Exception as e:
            logger.error(f"Could not retrieve MCP service count from mcp_client: {e}")
            mcp_service_count = -1 # Indicate error or unavailable

    # Dify Apps Info
    dify_apps_configured_names = []
    mcp_connections = app_settings.get_config("mcp_connections", [])
    if isinstance(mcp_connections, list):
        for conn_config_entry in mcp_connections:
            if conn_config_entry.get("type") == "dify":
                client_cfg = conn_config_entry.get("client_config", {})
                dify_apps = client_cfg.get("apps", [])
                for app_info in dify_apps:
                    if isinstance(app_info, dict) and "name" in app_info:
                        dify_apps_configured_names.append(app_info["name"])

    return FrontendConfigResponse(
        llm_providers_available=llm_providers_available,
        default_llm_provider=default_llm_provider,
        rpa_platforms_configured=rpa_platforms_configured,
        mcp_service_count=mcp_service_count,
        dify_apps_configured=dify_apps_configured_names
    )

@app.post("/api/v1/config", status_code=202) # 202 Accepted for async tasks
async def update_agent_config(request_body: UpdateConfigRequest, request: Request):
    logger.warning(f"POST /api/v1/config called with: {request_body.dict()}. This is a sensitive operation!")
    app_settings = getattr(request.app.state, "app_settings", None)
    if not app_settings:
         raise HTTPException(status_code=500, detail="Server configuration error: AppSettings not initialized.")

    # TODO: Implement proper authentication/authorization here. This is critical for security.
    # For now, just logging and returning a conceptual success.

    logger.warning("Configuration update functionality is conceptual. No actual config changes will be made by this endpoint in this version.")
    # In a real application:
    # 1. Validate config_key_path and new_value.
    # 2. Check user permissions.
    # 3. Update the configuration source (e.g., settings.json file, or in-memory AppSettings if it supports dynamic updates).
    #    - If updating files, consider backup and rollback strategies.
    # 4. If AppSettings is updated in memory, ensure relevant components are re-initialized or notified if needed.
    #    This might involve complex logic like restarting parts of the agent or specific clients.
    # 5. For file-based changes, a separate "apply_config_changes" mechanism might be needed (e.g., agent restart).

    # Example: app_settings.update_setting(request_body.config_key_path, request_body.new_value)
    # This assumes AppSettings has such a method and can handle hot updates or flag for restart.

    return {"status": "request_received_conceptual", "message": "Configuration update request received. Actual update mechanism not implemented in this version."}


# --- Existing Health Check Endpoint ---
@app.get("/api/v1/health", summary="Health Check", tags=["Management"])
async def health_check():
    langgraph_app_status = "available" if hasattr(app.state, 'langgraph_app') and app.state.langgraph_app else "unavailable"
    return {
        "status": "ok",
        "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "langgraph_status": langgraph_app_status
    }

if __name__ == "__main__":
    import uvicorn
    logger.info("Starting FastAPI app directly for testing (use uvicorn from main.py in production)...")

    class MockLangGraphApp:
        async def ainvoke(self, input_state, config=None):
            logger.info(f"MockLangGraphApp invoked with: {input_state}, config: {config}")
            user_msg = input_state.get("raw_im_message", {}).get("message", "no message")
            return {"final_response_to_user": f"Mocked reply to: {user_msg}", "platform": "test", "chat_id": config.get("configurable",{}).get("thread_id")}

    class MockAppSettings: # Basic mock for AppSettings
        def __init__(self):
            self.llm_provider = "DummyLLM"
            self.rpa_platform_configs = {"macos": {"enabled": True, "rpa_scripts_path": "config/rpa_macos_scripts.json"}}
            self.mcp_connections = [
                {"name": "dify_main", "type": "dify", "client_config": {"apps": [{"name": "test_dify_app"}]}}
            ]
            self.available_llm_providers_for_frontend = ["DummyLLM", "OpenAI"]
        def get_config(self, key, default=None): return getattr(self, key, default)

    class MockMCPClient:
        async def list_services(self): return [{"name": "mock_mcp_service"}]

    app.state.langgraph_app = MockLangGraphApp()
    app.state.app_settings = MockAppSettings()
    app.state.mcp_client = MockMCPClient() # For get_frontend_config

    uvicorn.run(app, host="0.0.0.0", port=8001)
