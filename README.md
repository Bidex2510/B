# Jarvis - Personal AI Assistant

A voice-enabled personal AI assistant powered by Claude, inspired by Iron Man's Jarvis.

## Features

- **Voice Interaction** - Talk to Jarvis and hear responses (speech-to-text + text-to-speech)
- **AI-Powered Chat** - Intelligent conversation powered by Claude (Anthropic)
- **System Automation** - Open apps, run commands, browse URLs
- **Persistent Memory** - Jarvis remembers facts about you across sessions

## Setup

```bash
# Install dependencies
pip install -r requirements.txt

# Set up your API key
cp .env.example .env
# Edit .env and add your Anthropic API key
```

### Voice mode prerequisites (optional)

Voice mode requires a working microphone and speakers. On Linux you may need:

```bash
sudo apt-get install portaudio19-dev python3-pyaudio espeak
```

## Usage

```bash
# Text mode (default)
python -m jarvis.main

# Voice mode
python -m jarvis.main --voice
```

## Built-in Commands

| Command | Description |
|---|---|
| `my name is <name>` | Tell Jarvis your name |
| `remember that <fact>` | Save a fact to memory |
| `what do you remember` | List saved memories |
| `system info` | Show system information |
| `reset` | Clear conversation history |
| `goodbye` / `exit` / `quit` | Shut down Jarvis |

Everything else is sent to the AI brain for a natural language response. Jarvis can also execute system commands, open apps, and browse URLs when you ask.
