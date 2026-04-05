"""Knowledge and conversational plugin - handles general questions."""

import re

from jarvis.core.plugin_base import PluginBase


KNOWLEDGE_BASE = {
    "who are you": "I am Jarvis, your personal AI assistant. I was built to help you manage your digital life, sir.",
    "what can you do": "I can monitor your system, manage tasks, control smart home devices, do calculations, tell time, and search the web. Say 'help' for details.",
    "who made you": "I was crafted with care, inspired by the legendary Jarvis from Iron Man. Built with Python and a desire to assist.",
    "meaning of life": "42, sir. At least according to Douglas Adams.",
    "tell me a joke": "Why do programmers prefer dark mode? Because light attracts bugs, sir.",
    "how are you": "All systems are running smoothly, sir. Thank you for asking.",
    "thank you": "You're welcome, sir. Always happy to help.",
    "thanks": "My pleasure, sir.",
    "help": None,  # handled specially
}


class KnowledgePlugin(PluginBase):

    name = "knowledge"
    description = "Answer general questions, provide help, and have conversations"

    TRIGGERS = [
        r"\b(who are you|what can you do|who made you|meaning of life)\b",
        r"\b(tell me a joke|joke)\b",
        r"\b(how are you|thank|thanks|help)\b",
        r"\b(what is|what are|who is|who was|define|explain)\b",
    ]

    def can_handle(self, text):
        return any(re.search(t, text, re.IGNORECASE) for t in self.TRIGGERS)

    def handle(self, text):
        lower = text.lower().strip("?.,! ")

        if lower == "help":
            return self._help()

        for key, response in KNOWLEDGE_BASE.items():
            if key in lower:
                if response is None:
                    return self._help()
                return response

        # General "what is" questions
        if re.search(r"\b(what is|what are|define|explain)\b", lower):
            topic = re.sub(r"\b(what is|what are|what's|define|explain|please|jarvis|a|an|the)\b", "", lower).strip()
            return (
                f"That's a great question about \"{topic}\", sir. "
                f"I'd recommend using the web search feature for detailed information. "
                f"Try saying: \"search for {topic}\""
            )

        return "I'm not sure about that, sir. Could you rephrase?"

    def _help(self):
        if not self.brain:
            return "Help is not available right now."

        lines = ["=== Jarvis Help ===\n", "Available modules:\n"]
        for name, plugin in self.brain.plugins.items():
            lines.append(f"  [{name}]")
            lines.append(f"    {plugin.description}\n")
        lines.append("Just speak naturally - I'll figure out the rest, sir.")
        return "\n".join(lines)
