"""Web search plugin - simulated web search capability."""

import re
import urllib.parse

from jarvis.core.plugin_base import PluginBase


class WebSearchPlugin(PluginBase):

    name = "web_search"
    description = "Search the web for information (generates search links)"

    TRIGGERS = [
        r"\b(search|google|look up|find|browse|web)\b",
        r"\b(search for|look up|find info)\b",
    ]

    def can_handle(self, text):
        return any(re.search(t, text, re.IGNORECASE) for t in self.TRIGGERS)

    def handle(self, text):
        query = re.sub(
            r"\b(search|google|look up|find|browse|web|for|please|jarvis|info|about|the|on)\b",
            "", text, flags=re.IGNORECASE,
        ).strip().strip("?.,!")

        if not query:
            return "What would you like me to search for, sir?"

        encoded = urllib.parse.quote_plus(query)
        return (
            f"Here are search links for \"{query}\", sir:\n\n"
            f"  Google : https://www.google.com/search?q={encoded}\n"
            f"  DuckDuckGo : https://duckduckgo.com/?q={encoded}\n"
            f"  Wikipedia : https://en.wikipedia.org/wiki/{urllib.parse.quote(query.replace(' ', '_'))}\n\n"
            f"Shall I look into anything specific about this topic?"
        )
