"""System actions and task automation."""

import json
import subprocess
import platform
import webbrowser
import datetime
import re


def try_parse_action(response: str) -> dict | None:
    """Try to extract a JSON action block from the AI response."""
    match = re.search(r'\{[^{}]*"action"[^{}]*\}', response)
    if match:
        try:
            return json.loads(match.group())
        except json.JSONDecodeError:
            return None
    return None


def execute_action(action: dict) -> str:
    """Execute a parsed action and return the result."""
    action_type = action.get("action")

    if action_type == "system_command":
        return run_command(action.get("command", ""))
    elif action_type == "open_app":
        return open_application(action.get("app", ""))
    elif action_type == "open_url":
        return open_url(action.get("url", ""))
    else:
        return f"Unknown action: {action_type}"


def run_command(command: str) -> str:
    """Run a shell command and return output."""
    if not command:
        return "No command provided."
    try:
        result = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
            timeout=30,
        )
        output = result.stdout.strip() or result.stderr.strip()
        return output or "Command executed successfully."
    except subprocess.TimeoutExpired:
        return "Command timed out."
    except Exception as e:
        return f"Error running command: {e}"


def open_application(app_name: str) -> str:
    """Open an application by name."""
    system = platform.system()
    try:
        if system == "Darwin":
            subprocess.Popen(["open", "-a", app_name])
        elif system == "Linux":
            subprocess.Popen([app_name.lower()])
        elif system == "Windows":
            subprocess.Popen(["start", app_name], shell=True)
        return f"Opening {app_name}."
    except Exception as e:
        return f"Couldn't open {app_name}: {e}"


def open_url(url: str) -> str:
    """Open a URL in the default browser."""
    webbrowser.open(url)
    return f"Opening {url} in your browser."


def get_system_info() -> str:
    """Get basic system information."""
    info = {
        "system": platform.system(),
        "node": platform.node(),
        "release": platform.release(),
        "machine": platform.machine(),
        "time": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }
    return "\n".join(f"  {k}: {v}" for k, v in info.items())
