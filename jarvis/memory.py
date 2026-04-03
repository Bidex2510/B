"""Persistent memory for Jarvis."""

import json
from pathlib import Path


class Memory:
    def __init__(self, path: str = "memory.json"):
        self.path = Path(path)
        self.data: dict = {}
        self._load()

    def _load(self):
        if self.path.exists():
            self.data = json.loads(self.path.read_text())

    def save(self):
        self.path.write_text(json.dumps(self.data, indent=2))

    def get(self, key: str, default=None):
        return self.data.get(key, default)

    def set(self, key: str, value):
        self.data[key] = value
        self.save()

    def append_to(self, key: str, value):
        """Append a value to a list stored at key."""
        if key not in self.data:
            self.data[key] = []
        self.data[key].append(value)
        self.save()

    def remember(self, fact: str):
        """Store a fact the user told Jarvis to remember."""
        self.append_to("remembered_facts", fact)

    def get_facts(self) -> list[str]:
        return self.get("remembered_facts", [])
