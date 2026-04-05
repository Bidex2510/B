"""Task manager plugin - reminders, todos, and notes."""

import re
import json
import os
from datetime import datetime

from jarvis.core.plugin_base import PluginBase

DATA_FILE = os.path.expanduser("~/.jarvis_tasks.json")


class TaskManagerPlugin(PluginBase):

    name = "task_manager"
    description = "Manage tasks, todos, and notes (add/list/complete/delete tasks)"

    TRIGGERS = [
        r"\b(tasks?|todos?|remind|reminder|note|complete|done)\b",
        r"\b(remember|don't forget|need to)\b",
    ]

    def __init__(self):
        super().__init__()
        self.tasks = self._load()

    def can_handle(self, text):
        return any(re.search(t, text, re.IGNORECASE) for t in self.TRIGGERS)

    def handle(self, text):
        lower = text.lower()

        if re.search(r"\b(add|create|new|remember|need to)\b", lower):
            return self._add_task(text)
        elif re.search(r"\b(list|show|view|all)\b.*\b(task|todo|note|reminder)\b", lower):
            return self._list_tasks()
        elif re.search(r"\b(complete|done|finish|check off)\b", lower):
            return self._complete_task(text)
        elif re.search(r"\b(delete|remove|clear)\b", lower):
            return self._delete_task(text)
        else:
            return self._list_tasks()

    def _add_task(self, text):
        # Extract task content by removing trigger words
        content = re.sub(
            r"\b(add|create|new|task|todo|remind(er)?|remember|note|need to|me to|please|jarvis)\b",
            "", text, flags=re.IGNORECASE,
        ).strip().strip(".,!?")

        if not content:
            return "What would you like me to remember, sir?"

        task = {
            "id": len(self.tasks) + 1,
            "content": content,
            "created": datetime.now().isoformat(),
            "completed": False,
        }
        self.tasks.append(task)
        self._save()
        return f"Task added, sir: \"{content}\" [#{task['id']}]"

    def _list_tasks(self):
        if not self.tasks:
            return "Your task list is empty, sir. Shall I add something?"

        lines = ["Your current tasks:\n"]
        for t in self.tasks:
            status = "done" if t["completed"] else "pending"
            marker = "[x]" if t["completed"] else "[ ]"
            lines.append(f"  {marker} #{t['id']}: {t['content']} ({status})")
        pending = sum(1 for t in self.tasks if not t["completed"])
        lines.append(f"\n  {pending} pending, {len(self.tasks) - pending} completed.")
        return "\n".join(lines)

    def _complete_task(self, text):
        task_id = self._extract_id(text)
        if task_id is None:
            return "Which task should I mark as complete? Please provide the task number."
        for t in self.tasks:
            if t["id"] == task_id:
                t["completed"] = True
                self._save()
                return f"Task #{task_id} marked as complete: \"{t['content']}\""
        return f"I couldn't find task #{task_id}, sir."

    def _delete_task(self, text):
        if re.search(r"\b(all|everything|clear)\b", text, re.IGNORECASE):
            count = len(self.tasks)
            self.tasks.clear()
            self._save()
            return f"All {count} tasks have been cleared, sir."

        task_id = self._extract_id(text)
        if task_id is None:
            return "Which task should I delete? Please provide the task number."
        for i, t in enumerate(self.tasks):
            if t["id"] == task_id:
                removed = self.tasks.pop(i)
                self._save()
                return f"Task #{task_id} deleted: \"{removed['content']}\""
        return f"I couldn't find task #{task_id}, sir."

    def _extract_id(self, text):
        match = re.search(r"#?(\d+)", text)
        return int(match.group(1)) if match else None

    def _load(self):
        if os.path.exists(DATA_FILE):
            with open(DATA_FILE) as f:
                return json.load(f)
        return []

    def _save(self):
        with open(DATA_FILE, "w") as f:
            json.dump(self.tasks, f, indent=2)
