# Jarvis - Personal AI Assistant

A Python-powered personal assistant inspired by Iron Man's Jarvis. Built with a modular plugin architecture for easy extensibility.

## Quick Start

```bash
python -m jarvis
```

No external dependencies required - runs on Python 3.7+ standard library.

## Features

| Module | Capabilities |
|--------|-------------|
| **System Monitor** | CPU, memory, disk, uptime, and full system diagnostics |
| **Task Manager** | Add, list, complete, and delete tasks (persisted to disk) |
| **Smart Home** | Control lights, thermostat, locks, music, and security |
| **Calculator** | Basic and scientific math (sqrt, sin, cos, log, etc.) |
| **Date/Time** | Current time, date, day, and date calculations |
| **Web Search** | Generate search links for Google, DuckDuckGo, Wikipedia |
| **Knowledge** | General Q&A, jokes, help system |

## Example Commands

```
> What time is it?
> Show system status
> Add task buy groceries
> Turn on the lights
> Calculate 42 * 13.7
> Search for quantum computing
> Tell me a joke
> Set thermostat to 68 degrees
> Lock the front door
> Help
```

## Architecture

```
jarvis/
  core/
    brain.py          # Central NLP router
    assistant.py      # Main orchestrator
    plugin_base.py    # Abstract plugin interface
  plugins/
    system_monitor.py # System diagnostics
    task_manager.py   # Todo/task management
    datetime_plugin.py# Date and time
    calculator.py     # Math calculations
    smart_home.py     # Home automation sim
    knowledge.py      # General knowledge/help
    web_search.py     # Web search links
  utils/
    formatting.py     # Terminal colors/formatting
  config/
    settings.py       # Configuration
  __main__.py         # CLI entry point
```

## Extending Jarvis

Create a new plugin by inheriting from `PluginBase`:

```python
from jarvis.core.plugin_base import PluginBase

class MyPlugin(PluginBase):
    name = "my_plugin"
    description = "Does something cool"

    def can_handle(self, text):
        return "magic" in text

    def handle(self, text):
        return "Abracadabra, sir!"
```

Then register it in `jarvis/core/assistant.py`.
