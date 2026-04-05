"""Date and time plugin."""

import re
from datetime import datetime, timedelta

from jarvis.core.plugin_base import PluginBase


class DateTimePlugin(PluginBase):

    name = "datetime"
    description = "Tell the current date, time, day, and do time calculations"

    TRIGGERS = [
        r"\b(time|date|day|today|tomorrow|yesterday|clock|what day|what time|what date)\b",
        r"\b(what's the time|current time|current date)\b",
    ]

    def can_handle(self, text):
        return any(re.search(t, text, re.IGNORECASE) for t in self.TRIGGERS)

    def handle(self, text):
        lower = text.lower()
        now = datetime.now()

        if "tomorrow" in lower:
            tmrw = now + timedelta(days=1)
            return f"Tomorrow is {tmrw.strftime('%A, %B %d, %Y')}, sir."
        elif "yesterday" in lower:
            yest = now - timedelta(days=1)
            return f"Yesterday was {yest.strftime('%A, %B %d, %Y')}, sir."
        elif "date" in lower or "today" in lower:
            return f"Today is {now.strftime('%A, %B %d, %Y')}, sir."
        elif "day" in lower:
            return f"Today is {now.strftime('%A')}, sir."
        else:
            return f"The current time is {now.strftime('%I:%M %p')}, sir. Today is {now.strftime('%A, %B %d, %Y')}."
