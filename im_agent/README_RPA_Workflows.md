# Using Automator with IM-Agent

## 1. Introduction to Automator

**What is Automator?**
Automator is a built-in application on macOS that allows you to automate repetitive tasks by creating workflows. You can string together a series of actions – from simple file operations to complex scripting – without needing to write extensive code.

**Role in IM-Agent:**
IM-Agent can leverage Automator to perform actions on your Mac based on commands received through instant messaging. This allows you to control your computer remotely, run scripts, open applications, and much more, simply by sending a message to the agent.

The `AutomatorRunner` component within IM-Agent is responsible for discovering and executing these Automator workflows and other scripts.

## 2. Creating Basic Workflows

### 2.1. Launching Automator
1.  Open Finder.
2.  Go to the "Applications" folder.
3.  Double-click "Automator.app".

### 2.2. Choosing Document Type
When Automator launches, it will ask you to choose a type for your document:
*   **Workflow (`.workflow`):** A sequence of actions that can be run from within Automator itself or called by other processes (like our agent using the `automator` command-line tool). Workflows typically process input passed from one action to the next.
*   **Application (`.app`):** A self-contained workflow that runs like a regular application when you double-click it or when opened by the `open` command. This is often more convenient for standalone tasks.
*   **Quick Action (Service):** Workflows that are added to the context menu (e.g., when you right-click a file in Finder).
*   Other types include Print Plugin, Calendar Alarm, etc.

For IM-Agent, **Workflow** or **Application** are the most relevant types. Shell scripts (`.sh`) and AppleScript files (`.scpt`) are also directly supported by `AutomatorRunner` via `osascript` or direct execution.

### 2.3. Adding Actions
Automator has a library of pre-built actions. You can find them in the leftmost pane, categorized by application or type.
1.  **Drag and Drop:** Find an action and drag it into the main workflow area on the right.
2.  **Chain Actions:** The output of one action typically becomes the input for the next.

**Commonly Used Actions:**
*   **Launch Application:** (e.g., from "Utilities") Opens a specified application.
*   **Run Shell Script:** (e.g., from "Utilities") Allows you to embed shell commands (bash, zsh, etc.). You can pass input to this script.
*   **Run AppleScript:** (e.g., from "Utilities") Allows you to embed AppleScript code.
*   **Get Specified Text:** (e.g., from "Text") Provides a block of text as input to the next action. Useful for parameter passing.
*   **Type Keystroke:** (e.g., from "Utilities" in newer macOS versions, or search) Simulates typing keystrokes, including special keys. Useful for controlling UI elements that are not easily scriptable.

### 2.4. Using "Watch Me Do" (Use with Caution)
Automator includes a "Watch Me Do" feature that records your mouse clicks and keystrokes to automate UI interactions.
1.  Click the "Record" button in the top-right corner of Automator.
2.  Perform the actions you want to automate.
3.  Stop the recording.

**Caveats:**
*   **Reliability:** "Watch Me Do" workflows are often fragile. They break if UI elements change, window positions shift, or timing is off.
*   **Specificity:** They depend heavily on the exact state of the UI.
*   **Alternatives:** Scripting (AppleScript, Shell Script) is generally more robust if the application or system offers scripting interfaces.

### 2.5. Saving Workflows
*   **As a Workflow (`.workflow`):** `File > Save...`. Choose "Workflow" as the file format. These are typically stored in `~/Library/Services/` if you want them in context menus, or any other folder if called directly by the agent.
*   **As an Application (`.app`):** `File > Save...`. Change the "File Format" dropdown to "Application". These can be saved anywhere, like your `Applications` folder or a dedicated project `workflows/` folder.

## 3. Interacting with Automator from IM-Agent

The `AutomatorRunner` class in IM-Agent handles the execution of your saved Automator workflows, applications, AppleScripts, and shell scripts.

### 3.1. Execution Mechanism
*   **`subprocess` Module:** Python's `subprocess` module is used to run external commands.
*   **`automator` CLI:** For `.workflow` files, the agent primarily uses `/usr/bin/automator`.
*   **`open` CLI:** For `.app` files (Automator applications), the agent uses `/usr/bin/open`.
*   **`osascript` CLI:** For AppleScript files (`.scpt`, `.applescript`) and direct AppleScript commands, the agent uses `/usr/bin/osascript`.
*   **Direct Execution/Shell:** For shell scripts (`.sh`), they are either executed directly (if executable) or via `/bin/sh` or `/bin/bash`.

### 3.2. `automator_map.json`
To make your workflows accessible to the IM-Agent, you need to define them in the `automator_map.json` file. This file maps a user-friendly `workflow_name` (which you'll use in your IM commands) to the actual script or workflow file and its type.

**Location:** `im_agent/config/automator_map.json` (You should copy `automator_map.json.example` to this location and customize it).

**Example Entry:**
```json
{
    "open_my_notes_app": {
        "path": "/Applications/MyNotes.app",
        "type": "app",
        "description": "Opens the custom MyNotes application."
    },
    "get_current_song_applescript": {
        "path": "workflows/scripts/getCurrentSong.scpt",
        "type": "osascript_file",
        "description": "Gets the current song from Music.app using AppleScript."
    }
}
```
*   `path`: The absolute path to your `.workflow`, `.app`, `.scpt`, or `.sh` file. You can use `~` for your home directory (e.g., `~/Scripts/my_script.sh`). Environment variables like `$HOME` are also expanded.
*   `type`: Specifies how the `AutomatorRunner` should execute the file. Supported types:
    *   `app`: An Automator workflow saved as an application (`.app`). Executed with `open <path> [--args ...]`.
    *   `workflow`: An Automator workflow file (`.workflow`). Executed with `automator [-i input] <path>`.
    *   `osascript_file`: An AppleScript text file (`.scpt`, `.applescript`). Executed with `osascript <path> [args...]`.
    *   `osascript_command`: A string containing an AppleScript command. Executed with `osascript -e "<command_string>"`. Arguments are generally not directly passed to `-e` scripts unless the command string itself is designed to use them (less common for generic use).
    *   `shell_script`: A shell script file (`.sh`). Executed as `<path> [args...]` (if executable) or `sh <path> [args...]`.
    *   `osascript_shell`: A string containing a shell command to be executed via AppleScript's `do shell script`. The `path` field contains the shell command. Executed with `osascript -e 'do shell script "<shell_command_string>"'`.
*   `description`: A brief explanation of what the workflow does.
*   `timeout_seconds` (optional): Custom timeout for the workflow execution (default is 60 seconds).

## 4. Parameter Passing to Workflows (Crucial)

Passing data from your IM command to your Automator workflow or script is essential for dynamic automation. Here are several methods:

### Method 1: "Get Specified Text" as Input to `.workflow`
*   **Concept:** The first action in your `.workflow` file can be "Get Specified Text". The `AutomatorRunner` can pass input to this action.
*   **How to:**
    1.  In Automator, create a new **Workflow**.
    2.  Add the "Get Specified Text" action. You can leave its content empty or put a default/placeholder.
    3.  Add subsequent actions that will use the output of "Get Specified Text" as their input.
    4.  Save the workflow (e.g., `MyDataWorkflow.workflow`).
*   **IM-Agent (`automator_map.json`):**
    ```json
    "process_text_workflow": {
        "path": "/path/to/MyDataWorkflow.workflow",
        "type": "workflow",
        "description": "Processes text passed as input."
    }
    ```
*   **Python (`AutomatorRunner`):** The `run_workflow` method passes arguments using the `-i` flag of the `automator` command if arguments are provided.
    `automator -i "Your text input" /path/to/MyDataWorkflow.workflow`
    The text "Your text input" will appear in the "Get Specified Text" action when the workflow runs.
*   **Limitations:** The `-i` flag takes a single string. If you have multiple distinct parameters, you might need to pass them as a delimited string (e.g., "param1|param2") and parse it in a subsequent "Run Shell Script" or "Run AppleScript" action.

### Method 2: "Run Shell Script" Action
*   **Concept:** Use the "Run Shell Script" action within Automator. This action can receive input from the previous action or accept arguments if the script is designed for it.
*   **How to:**
    1.  Add a "Run Shell Script" action to your workflow.
    2.  In the action's settings:
        *   Choose your shell (e.g., `/bin/bash`, `/bin/zsh`).
        *   **Pass input:** Select "to stdin" or "as arguments".
            *   **to stdin:** The output of the previous action is piped to your script's standard input. You'd read it with `read` or similar commands.
            *   **as arguments:** The output of the previous action is passed as command-line arguments (`$1`, `$2`, etc.) to your script.
*   **Example (Pass input: as arguments):**
    *   Workflow:
        1.  "Get Specified Text" (provides "hello world")
        2.  "Run Shell Script" (Pass input: as arguments)
            ```bash
            #!/bin/bash
            echo "First argument: $1"
            echo "Second argument: $2"
            # If input was "hello world", $1 is "hello", $2 is "world" (if input is split by spaces)
            # Or, if the previous action passes a single string, $1 will be that whole string.
            ```
*   **If your *entire Automator workflow* is just this shell script (saved as an Application or run as a `.sh` file):**
    *   **IM-Agent (`automator_map.json` for a `.sh` file):**
        ```json
        "my_shell_task": {
            "path": "/path/to/myscript.sh",
            "type": "shell_script",
            "description": "Runs myscript.sh with arguments."
        }
        ```
    *   **Shell Script (`myscript.sh`):**
        ```bash
        #!/bin/bash
        echo "Script name: $0"
        echo "Argument 1: $1"
        echo "Argument 2: $2"
        # ... do something with $1, $2 ...
        ```
    *   **Agent Call:** When you run this via IM-Agent with arguments `["arg_one", "arg_two"]`, `AutomatorRunner` executes:
        `/path/to/myscript.sh "arg_one" "arg_two"`

### Method 3: AppleScript (`.scpt` files or "Run AppleScript" action)

AppleScript is very powerful for macOS automation and parameter passing.

*   **A. Standalone `.scpt` File (Recommended for complex logic with params):**
    1.  Create an AppleScript file (e.g., `MyAppleScript.scpt`) using Script Editor.
    2.  Define an `on run` handler that accepts arguments.
        ```applescript
        -- MyAppleScript.scpt
        on run argv -- argv is a list of strings
            if (count of argv) > 0 then
                log "First argument: " & (item 1 of argv)
            else
                log "No arguments provided."
            end if
            if (count of argv) > 1 then
                log "Second argument: " & (item 2 of argv)
            end if
            return "AppleScript processed: " & (item 1 of argv) -- Example return
        end run
        ```
    3.  **IM-Agent (`automator_map.json`):**
        ```json
        "my_applescript_task": {
            "path": "/path/to/MyAppleScript.scpt",
            "type": "osascript_file",
            "description": "Runs MyAppleScript.scpt with arguments."
        }
        ```
    4.  **Agent Call:** When run with arguments `["hello", "applescript"]`, `AutomatorRunner` executes:
        `osascript /path/to/MyAppleScript.scpt "hello" "applescript"`

*   **B. Automator Application (`.app`) Called via AppleScript (for apps not designed for CLI args):**
    If you have an Automator workflow saved as an application (`MyApp.app`) and it's not set up to easily receive CLI arguments via `open --args`, you can use `osascript` to tell it to run with properties.
    1.  The `.app` itself needs to be designed to handle these properties, usually if its first action is AppleScript aware or if it's an AppleScript application.
    2.  **IM-Agent (`automator_map.json`):**
        ```json
        "run_my_automator_app_with_params": {
            "path": "tell application \"/path/to/MyApp.app\" to run with properties {the_message:\"Hello from agent\", the_count:5}",
            "type": "osascript_command",
            "description": "Runs MyApp.app with specific properties via AppleScript."
        }
        ```
        *Note:* The `path` here is the AppleScript command itself. Arguments from the `run_workflow` method are not easily substituted into this `osascript_command` string directly by `AutomatorRunner`. You'd typically craft different `osascript_command` entries for different parameter sets, or use an `osascript_file` that takes generic arguments and then constructs this `tell application` call.

*   **C. "Run AppleScript" Action within a `.workflow`:**
    ```applescript
    on run {input, parameters}
        -- 'input' is the output from the previous Automator action.
        -- 'parameters' is generally not used when called from 'automator' CLI.

        -- To use data passed via `automator -i "my data" ...`
        set myData to item 1 of input -- if input is a list of one item

        log "Received input: " & myData
        return "Processed: " & myData -- This becomes input for the next action
    end run
    ```

### Recommendations on Parameter Passing:
*   **For simple text input to a `.workflow`:** Use "Get Specified Text" as the first action and rely on `automator -i "..."`.
*   **For scripts (`.sh`, `.scpt`):** Define them to accept command-line arguments. Use `type: "shell_script"` or `type: "osascript_file"` in `automator_map.json`. This is often the most robust and clear method for multiple parameters.
*   **For `.app` files:** If the app is script-based and handles `sys.argv` (Python) or `argv` (AppleScript `on run argv`), use `open ... --args ...` by setting `type: "app"`. If not, consider wrapping its execution in an AppleScript (`.scpt`) that can pass parameters appropriately, then call that script.
*   **`osascript_command`:** Best for fixed AppleScript commands. Dynamic parameter injection is limited unless the command string itself is built to expect appended arguments (which is not standard for arbitrary AppleScript commands).
*   **`osascript_shell`:** Use for running shell commands that might need AppleScript's `do shell script` context, perhaps for quoting or specific environment reasons.

## 5. Error Handling & Debugging

*   **Automator's "Results" and "Log":**
    *   When editing a workflow in Automator, each action shows its "Results" after running.
    *   The "Log" pane at the bottom of the Automator window shows messages, warnings, and errors from all actions. Check here first if a workflow misbehaves.
*   **Test Independently:** Run your `.workflow`, `.app`, `.scpt`, or `.sh` file directly from Terminal or by double-clicking (for `.app`) before integrating with IM-Agent. This helps isolate whether the issue is in the script/workflow itself or in how the agent calls it.
    *   Example for `.workflow`: `automator /path/to/myflow.workflow`
    *   Example for `.app`: `open /path/to/myapp.app --args test_arg`
    *   Example for `.scpt`: `osascript /path/to/myscript.scpt test_arg`
*   **Simplify:** If a complex workflow fails, break it down. Test each action or small group of actions separately.
*   **Output from IM-Agent:** The `AutomatorRunner` returns `stdout` and `stderr` from the executed process. Check the agent's logs for this output when troubleshooting.

## 6. Naming Conventions & Storage

*   **Storage:**
    *   **`~/Library/Services/`:** Workflows (`.workflow`) saved here can appear in the Services context menu in Finder and other apps. This is standard but might require IM-Agent to have specific permissions or for paths to be correctly configured.
    *   **Dedicated Project Folder (Recommended for IM-Agent):** Create a folder like `im_agent/workflows/` or `~/AutomationScripts/im_agent/` to store your custom workflows, applications, and scripts. This makes them easy to manage, version control (if desired), and reference in `automator_map.json`.
        *   Example: `im_agent/workflows/scripts/my_backup.sh`
        *   Example: `im_agent/workflows/apps/MyDataEntry.app`
*   **Naming:** Use clear, descriptive names for your workflow files and for the logical names in `automator_map.json`.
    *   `open_discord.app` (file) -> `"open_discord"` (logical name)
    *   `create_reminder_from_text.scpt` (file) -> `"create_reminder"` (logical name)

## 7. Example Workflows (Illustrative)

### Example 1: Open Application (Discord)
*   **Type:** Automator Application (`.app`)
*   **Action:** "Launch Application" (select Discord.app)
*   **Save as:** `OpenDiscord.app` (e.g., in `~/Applications/` or `im_agent/workflows/apps/`)
*   **`automator_map.json` entry:**
    ```json
    "open_discord": {
        "path": "/Applications/Discord.app",
        "type": "app",
        "description": "Opens the Discord application."
    }
    ```
    (Note: For common apps in `/Applications/`, `type: "app"` and the direct path is simple. No Automator creation needed unless you want to do more before/after launching.)

### Example 2: Create New Text File on Desktop with Timestamp
*   **Type:** AppleScript (`.scpt`) for simplicity, or an Automator Application containing "Run AppleScript".
*   **Script (`CreateTimestampedFile.scpt`):**
    ```applescript
    on run argv
        set timestamp to ((current date) as string)
        set fileName to "Note_" & (do shell script "date +%Y%m%d_%H%M%S") & ".txt"
        set fileContent to "Created at: " & timestamp
        if (count of argv) > 0 then
            set fileContent to fileContent & "\\n\\nInput: " & (item 1 of argv)
        end if

        tell application "Finder"
            try
                set desktopPath to (path to desktop folder as text)
                set newFile to make new file at desktopPath with properties {name:fileName, text:fileContent}
            on error errMsg number errNum
                return "Error: " & errMsg
            end try
        end tell
        return "File created: " & fileName
    end run
    ```
*   **Save as:** `CreateTimestampedFile.scpt` (e.g., in `im_agent/workflows/scripts/`)
*   **`automator_map.json` entry:**
    ```json
    "create_desktop_note": {
        "path": "workflows/scripts/CreateTimestampedFile.scpt",
        "type": "osascript_file",
        "description": "Creates a new text file on the desktop with a timestamp. Optionally takes one argument for content."
    }
    ```

### Example 3: Simple Reminder (using AppleScript)
*   **Type:** AppleScript (`.scpt`)
*   **Script (`AddReminder.scpt`):**
    ```applescript
    on run argv
        if (count of argv) is 0 then
            return "Error: Please provide reminder text."
        end if
        set reminderText to item 1 of argv

        tell application "Reminders"
            tell default list
                make new reminder with properties {name:reminderText}
            end tell
        end tell
        return "Reminder added: " & reminderText
    end run
    ```
*   **Save as:** `AddReminder.scpt` (e.g., in `im_agent/workflows/scripts/`)
*   **`automator_map.json` entry:**
    ```json
    "add_reminder": {
        "path": "workflows/scripts/AddReminder.scpt",
        "type": "osascript_file",
        "description": "Adds a reminder to the default Reminders list. Expects one argument: the reminder text."
    }
    ```

---

This guide should help you get started with creating and integrating Automator workflows and other scripts with the IM-Agent! Remember to test your scripts thoroughly.I have already implemented the `AutomatorRunner` class and created the `automator_map.json.example` file. The `README_Automator.md` has just been created.

The remaining step is to implement the Automator Factory in `im_agent/src/agent/automator/__init__.py`.
