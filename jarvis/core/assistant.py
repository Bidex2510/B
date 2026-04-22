"""Jarvis Assistant - Main orchestrator that ties everything together."""

from jarvis.core.brain import JarvisBrain
from jarvis.plugins.system_monitor import SystemMonitorPlugin
from jarvis.plugins.task_manager import TaskManagerPlugin
from jarvis.plugins.datetime_plugin import DateTimePlugin
from jarvis.plugins.calculator import CalculatorPlugin
from jarvis.plugins.smart_home import SmartHomePlugin
from jarvis.plugins.knowledge import KnowledgePlugin
from jarvis.plugins.web_search import WebSearchPlugin
from jarvis.plugins.trading.plugin import TradingBotPlugin


class Jarvis:
    """The main Jarvis assistant class."""

    BANNER = r"""
     ██╗ █████╗ ██████╗ ██╗   ██╗██╗███████╗
     ██║██╔══██╗██╔══██╗██║   ██║██║██╔════╝
     ██║███████║██████╔╝██║   ██║██║███████╗
██   ██║██╔══██║██╔══██╗╚██╗ ██╔╝██║╚════██║
╚█████╔╝██║  ██║██║  ██║ ╚████╔╝ ██║███████║
 ╚════╝ ╚═╝  ╚═╝╚═╝  ╚═╝  ╚═══╝  ╚═╝╚══════╝
    Personal AI Assistant v1.0
    """

    def __init__(self):
        self.brain = JarvisBrain()
        self._load_plugins()

    def _load_plugins(self):
        """Load all built-in plugins."""
        plugins = [
            SystemMonitorPlugin(),
            TaskManagerPlugin(),
            DateTimePlugin(),
            CalculatorPlugin(),
            SmartHomePlugin(),
            KnowledgePlugin(),
            WebSearchPlugin(),
            TradingBotPlugin(),
        ]
        for plugin in plugins:
            self.brain.register_plugin(plugin.name, plugin)

    def chat(self, user_input):
        """Send a message to Jarvis and get a response."""
        return self.brain.process(user_input)

    def get_status(self):
        """Get a system status summary."""
        sys_plugin = self.brain.plugins.get("system_monitor")
        if sys_plugin:
            return sys_plugin.handle("system status")
        return "All systems nominal, sir."

    def list_capabilities(self):
        """List all available capabilities."""
        lines = ["Here are my current capabilities, sir:\n"]
        for name, plugin in self.brain.plugins.items():
            lines.append(f"  [{name}] {plugin.description}")
        return "\n".join(lines)
