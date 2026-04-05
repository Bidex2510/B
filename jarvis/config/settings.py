"""Jarvis configuration settings."""

JARVIS_CONFIG = {
    "name": "Jarvis",
    "version": "1.0.0",
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
    },
    "history": {
        "max_entries": 1000,
        "save_to_file": True,
    },
}
