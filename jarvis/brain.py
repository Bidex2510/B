"""Core AI brain powered by Claude."""

import anthropic
from jarvis.memory import Memory


SYSTEM_PROMPT = """You are Jarvis, a highly intelligent and loyal personal AI assistant, \
inspired by the AI from Iron Man. You are helpful, witty, and efficient. \
You speak in a professional yet friendly manner, occasionally with dry humor.

You can help with:
- Answering questions and having conversations
- System tasks (opening apps, running commands, checking system info)
- Web searches and information lookup
- Setting reminders and managing tasks
- General knowledge and problem solving

When the user asks you to perform a system action, respond with a JSON block like:
{"action": "system_command", "command": "the shell command to run"}
{"action": "open_app", "app": "application name"}
{"action": "open_url", "url": "https://example.com"}

For normal conversation, just respond naturally.

Keep responses concise and to the point, like a real assistant would."""


class Brain:
    def __init__(self, memory: Memory):
        self.client = anthropic.Anthropic()
        self.memory = memory
        self.conversation_history: list[dict] = []

    def _build_system_prompt(self) -> str:
        user_info = self.memory.get("user_info", {})
        preferences = self.memory.get("preferences", {})

        context_parts = [SYSTEM_PROMPT]
        if user_info:
            context_parts.append(f"\nUser info you remember: {user_info}")
        if preferences:
            context_parts.append(f"\nUser preferences: {preferences}")

        return "\n".join(context_parts)

    def think(self, user_input: str) -> str:
        self.conversation_history.append({"role": "user", "content": user_input})

        # Keep conversation history manageable (last 20 exchanges)
        if len(self.conversation_history) > 40:
            self.conversation_history = self.conversation_history[-40:]

        response = self.client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=1024,
            system=self._build_system_prompt(),
            messages=self.conversation_history,
        )

        assistant_message = response.content[0].text
        self.conversation_history.append(
            {"role": "assistant", "content": assistant_message}
        )

        return assistant_message

    def reset_conversation(self):
        self.conversation_history = []
