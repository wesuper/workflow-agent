# macOS Desktop Automation Smart Agent (IM-Agent)

## Overview

IM-Agent is a Python-based smart agent designed to automate tasks on a macOS desktop through commands received via various instant messaging (IM) platforms. It leverages Large Language Models (LLMs) to understand user requests, interact with external services (MCPs - Master Control Programs), and execute local Automator workflows or scripts. The agent aims to provide a conversational interface for complex task automation.

## Core Features

*   **Instant Messaging Integration:** Supports multiple IM platforms (e.g., Discord, WeChat Work, with a Dummy adapter for testing) for receiving commands and sending responses.
*   **LLM-Powered Understanding:** Utilizes LLMs (e.g., OpenAI GPT models, DummyLLM for testing) to parse user messages, maintain conversation context, and translate requests into actionable commands.
*   **MCP Service Interaction:** Can connect to and invoke external APIs or services (MCPs) to fetch data or perform actions beyond the local machine. Supports dynamic addition of new MCP services.
*   **macOS Automator & Scripting:** Executes macOS Automator workflows, AppleScripts, and shell scripts to perform local desktop automation tasks.
*   **Configurable & Extensible:** Designed with a modular architecture, allowing for new IM platforms, LLM providers, MCP services, and Automator workflows to be added.

## Technology Stack

*   **Python:** Version 3.12
*   **uv:** For project and environment management (alternative to pip/venv).
*   **Asyncio:** For concurrent operations, especially for IM adapters.
*   **Supported OS for Full Functionality:** macOS (Automator features are macOS-specific). Core agent can run on other OSes with Automator disabled.
*   **Key Python Libraries:**
    *   `openai` (for OpenAI LLM adapter)
    *   `requests` (for MCP service handler)

## Prerequisites

*   **macOS (Recommended):** For full functionality including Automator workflows.
*   **Python 3.12 or higher:** Download from [python.org](https://www.python.org/).
*   **uv:** Installation instructions at [astral.sh/uv](https://astral.sh/uv). After installing, ensure it's in your PATH.
    ```bash
    curl -LsSf https://astral.sh/uv/install.sh | sh
    # Source your shell profile (e.g., ~/.bash_profile, ~/.zshrc) or open a new terminal
    ```
*   **Git:** For cloning the repository.

## Setup Instructions

1.  **Clone the Repository:**
    ```bash
    git clone <repository_url> # Replace <repository_url> with the actual URL
    cd im_agent
    ```

2.  **Create and Activate Virtual Environment:**
    ```bash
    uv venv
    source .venv/bin/activate
    # On Windows, use: .venv\Scripts\activate
    ```

3.  **Install Dependencies:**
    It's recommended to use `pyproject.toml` with `uv sync` if all dependencies are listed there. If a `requirements.txt` is provided (see Step 4 of Finalization task):
    ```bash
    uv pip install -r requirements.txt 
    # Or, to sync directly with pyproject.toml:
    # uv sync pyproject.toml # This might be preferred if pyproject.toml is the source of truth
    ```

4.  **Configuration:**
    The agent uses configuration files stored in the `im_agent/config/` directory. Example files are provided with a `.example` extension. Copy these to create your local configurations:

    *   **Main Settings:**
        ```bash
        cp config/settings.json.example config/settings.json
        ```
        Edit `config/settings.json`:
        *   `llm_provider`: Choose your LLM provider (e.g., "OpenAI", "DummyLLM").
        *   `llm_config`: Configure settings for the chosen LLM.
            *   For OpenAI: Set `api_key_env_var` to the name of the environment variable holding your API key (e.g., "OPENAI_API_KEY").
        *   `llm_system_prompt_path`: Path to the system prompt file (e.g., "config/system_prompt.md").
        *   `im_settings`: Configure your desired IM platforms. Set `"enabled": true` for each platform you want to use.
            *   `"dummy"`: Good for initial testing.
            *   `"wechat_work"`: Requires `corp_id`, `agent_id`, `secret_env_var`.
            *   `"discord"`: Requires `bot_token_env_var`.
        *   `mcp_servers_config_path`: Path to MCP services definition (e.g., "config/mcp-servers.json").
        *   `whitelist_file_path`: Path to user whitelist Python file (e.g., "config/whitelist.py").
        *   `automator_workflows_map_path`: Path to Automator workflow map (e.g., "config/automator_map.json").
        *   `log_level`: Set desired logging level (e.g., "INFO", "DEBUG").
        *   `conversation_history_max_length`: Max number of messages (user + assistant) to keep per conversation.

    *   **LLM System Prompt (if using path from `settings.json`):**
        ```bash
        cp config/system_prompt.md.example config/system_prompt.md 
        ```
        Review and customize `config/system_prompt.md` if needed.

    *   **MCP Services:**
        ```bash
        cp config/mcp-servers.json.example config/mcp-servers.json
        ```
        Edit `config/mcp-servers.json` to define your MCP services.

    *   **User Whitelist:**
        ```bash
        cp config/whitelist.py.example config/whitelist.py
        ```
        Edit `config/whitelist.py` to add user IDs authorized for sensitive actions (like adding MCPs).

    *   **Automator Workflow Map (macOS only):**
        ```bash
        cp config/automator_map.json.example config/automator_map.json
        ```
        Edit `config/automator_map.json` to define your Automator workflows.

5.  **Set Environment Variables:**
    The agent relies on environment variables for sensitive information like API keys. Set these in your shell environment or using a `.env` file (ensure `.env` is in `.gitignore`).
    Example:
    ```bash
    export OPENAI_API_KEY="your_openai_api_key_here"
    export YOUR_WECHAT_WORK_SECRET_ENV_VAR="your_wechat_work_secret"
    export YOUR_DISCORD_BOT_TOKEN_ENV_VAR="your_discord_bot_token"
    # Add any other environment variables required by your MCP service configurations
    ```
    If using a `.env` file in the `im_agent` root, you might need a library like `python-dotenv` and load it at the beginning of `main.py` (not currently implemented).

## Running the Agent

Once setup is complete, run the agent from the `im_agent` root directory:
```bash
python src/agent/main.py --config_path config/settings.json
```
*   You can specify a different configuration file using the `--config_path` argument. If omitted, it defaults to `config/settings.json` relative to the project root.
*   The agent will initialize and connect to the enabled IM platforms.

## Basic Usage

*   **Dummy IM Adapter:** If the `dummy` IM adapter is enabled in `settings.json`, it will simulate receiving messages at intervals. You can see the agent's processing flow in the console logs.
*   **Other IM Platforms:** Interact with the agent by sending messages through the configured IM platform (e.g., send a message to your Discord bot).
*   **Example Commands (Natural Language):**
    *   "Hello, how are you?"
    *   "What can you do?"
    *   "What's the weather like in London?" (Requires `OpenWeatherMap_Current` or similar MCP)
    *   "Remind me to buy groceries at 6 PM." (Requires an Automator workflow like `create_reminder`)
    *   (For whitelisted user) "Add this MCP service: { \"name\": \"NewService\", ... }"

## Automator Integration (macOS)

For detailed information on creating and using Automator workflows with IM-Agent, please refer to the `README_Automator.md` file in this repository.

## Extensibility

*   **Adding New IM Adapters:** Create a new class in `src/agent/im/` inheriting from `IMInterface`, then add it to `SUPPORTED_IM_PLATFORMS` in `src/agent/im/__init__.py`.
*   **Adding New LLM Providers:** Create a new class in `src/agent/llm/` inheriting from `LLMInterface`, then add it to `SUPPORTED_LLM_PROVIDERS` in `src/agent/llm/__init__.py`.
*   **Adding New MCP Services:** Define new services in your `config/mcp-servers.json` file, or use the "Add MCP" command if you are a whitelisted user.
*   **Adding New Automator Workflows:** Define new workflows in your `config/automator_map.json` and place the corresponding script/workflow files in accessible locations.

## Troubleshooting

*   **Check Logs:** The agent logs extensively to the console. Log level can be adjusted in `config/settings.json`.
*   **Environment Variables:** Ensure all required environment variables (API keys, secrets) are correctly set and accessible to the agent process.
*   **File Paths:** Verify that paths in `config/settings.json` (for other configs, system prompt) and in `mcp-servers.json`/`automator_map.json` (for scripts) are correct relative to the project structure or are absolute.
*   **Permissions (macOS):** For Automator workflows interacting with applications or system services, macOS may require permissions to be granted (e.g., in System Settings > Privacy & Security > Automation or Accessibility).
*   **Dependency Issues:** If you encounter import errors, ensure your virtual environment is active and all dependencies from `requirements.txt` (or `pyproject.toml`) are installed correctly.

---
This README provides a comprehensive guide for users to set up, run, and extend the IM-Agent.
```
