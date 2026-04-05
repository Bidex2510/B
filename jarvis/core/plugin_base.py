"""Base class for all Jarvis plugins."""

from abc import ABC, abstractmethod


class PluginBase(ABC):
    """Abstract base class that all Jarvis plugins must inherit from."""

    def __init__(self):
        self.brain = None

    @property
    @abstractmethod
    def name(self):
        """Plugin name."""

    @property
    @abstractmethod
    def description(self):
        """Short description of what this plugin does."""

    @abstractmethod
    def can_handle(self, text):
        """Return True if this plugin can handle the given input."""

    @abstractmethod
    def handle(self, text):
        """Process the input and return a response string."""

    def get_help(self):
        """Return help text for this plugin."""
        return self.description
