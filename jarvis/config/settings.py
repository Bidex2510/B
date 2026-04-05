"""Jarvis configuration settings."""

JARVIS_CONFIG = {
    "name": "Jarvis",
    "version": "2.0.0",
    "personality": {
        "greeting_style": "formal",
        "use_sir": True,
        "verbose": False,
    },
    "features": {
        "system_monitor": True,
        "task_manager": True,
        "smart_home": True,
        "calculator": True,
        "web_search": True,
        "knowledge": True,
        "weather": True,
        "email": True,
        "news": True,
        "spotify": True,
        "home_assistant": True,
        "ai_chat": True,
        "study_tools": True,
        "finance": True,
        "utilities": True,
    },
    "server": {
        "host": "0.0.0.0",
        "port": 8000,
    },
    "history": {
        "max_entries": 1000,
        "save_to_file": True,
    },
}
