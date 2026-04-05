"""Jarvis Brain - Central intelligence that routes commands to plugins."""

import re
from datetime import datetime


class JarvisBrain:
    """Core AI brain that processes natural language and routes to plugins."""

    def __init__(self):
        self.plugins = {}
        self.command_history = []
        self.context = {}
        self.greeting_patterns = [
            r"\b(hello|hi|hey|greetings|good\s+(morning|afternoon|evening))\b",
        ]
        self.farewell_patterns = [
            r"\b(bye|goodbye|exit|quit|shutdown|see\s+you|good\s*night)\b",
        ]

    def register_plugin(self, name, plugin):
        """Register a plugin with the brain."""
        self.plugins[name] = plugin
        plugin.brain = self

    def process(self, user_input):
        """Process user input and return a response."""
        text = user_input.strip()
        if not text:
            return "I'm listening, sir. How can I help?"

        self.command_history.append({
            "input": text,
            "timestamp": datetime.now().isoformat(),
        })

        lower = text.lower()

        if self._matches(lower, self.farewell_patterns):
            return self._farewell()

        if self._matches(lower, self.greeting_patterns):
            return self._greet()

        for name, plugin in self.plugins.items():
            if plugin.can_handle(lower):
                try:
                    return plugin.handle(text)
                except Exception as e:
                    return f"I encountered an issue with the {name} module: {e}"

        return self._fallback(text)

    def _matches(self, text, patterns):
        return any(re.search(p, text, re.IGNORECASE) for p in patterns)

    def _greet(self):
        hour = datetime.now().hour
        if hour < 12:
            period = "morning"
        elif hour < 17:
            period = "afternoon"
        else:
            period = "evening"
        return f"Good {period}, sir. All systems are operational. How may I assist you?"

    def _farewell(self):
        return "Goodbye, sir. I'll be here if you need me."

    def _fallback(self, text):
        suggestions = []
        for name, plugin in self.plugins.items():
            suggestions.append(f"  - {plugin.description}")
        hint = "\n".join(suggestions)
        return (
            f"I'm not quite sure how to help with that, sir. "
            f"Here's what I can do:\n{hint}\n\n"
            f"Try rephrasing your request."
        )
