"""Main entry point for Jarvis."""

import sys
import os

from dotenv import load_dotenv

from jarvis.brain import Brain
from jarvis.memory import Memory
from jarvis.actions import try_parse_action, execute_action, get_system_info


BANNER = r"""
     ██╗ █████╗ ██████╗ ██╗   ██╗██╗███████╗
     ██║██╔══██╗██╔══██╗██║   ██║██║██╔════╝
     ██║███████║██████╔╝██║   ██║██║███████╗
██   ██║██╔══██║██╔══██╗╚██╗ ██╔╝██║╚════██║
╚█████╔╝██║  ██║██║  ██║ ╚████╔╝ ██║███████║
 ╚════╝ ╚═╝  ╚═╝╚═╝  ╚═╝  ╚═══╝  ╚═╝╚══════╝
    Your Personal AI Assistant (Powered by Claude)
"""

WAKE_WORDS = {"jarvis", "hey jarvis", "ok jarvis"}
EXIT_WORDS = {"goodbye", "exit", "quit", "bye", "shut down", "shutdown"}


def create_voice(use_voice: bool):
    """Create voice or text interface."""
    if use_voice:
        try:
            from jarvis.voice import Voice
            return Voice()
        except Exception as e:
            print(f"  Voice unavailable ({e}), falling back to text mode.")

    from jarvis.voice import TextFallback
    return TextFallback()


def run(voice_mode: bool = False):
    load_dotenv()

    if not os.environ.get("ANTHROPIC_API_KEY"):
        print("Error: Set ANTHROPIC_API_KEY in your .env file or environment.")
        sys.exit(1)

    print(BANNER)

    memory = Memory()
    brain = Brain(memory)
    voice = create_voice(voice_mode)

    # Greet the user
    user_name = memory.get("user_info", {}).get("name", "sir")
    voice.speak(f"Good day, {user_name}. Jarvis at your service. How can I help you?")

    while True:
        user_input = voice.listen()

        if not user_input:
            continue

        lower = user_input.lower().strip()

        # Exit commands
        if lower in EXIT_WORDS:
            voice.speak("Goodbye. I'll be here when you need me.")
            break

        # Built-in commands
        if lower == "system info":
            voice.speak("Here's your system information:")
            print(get_system_info())
            continue

        if lower == "reset":
            brain.reset_conversation()
            voice.speak("Conversation history cleared.")
            continue

        if lower.startswith("remember that "):
            fact = user_input[len("remember that "):]
            memory.remember(fact)
            voice.speak(f"I'll remember that: {fact}")
            continue

        if lower in ("what do you remember", "what do you know about me"):
            facts = memory.get_facts()
            if facts:
                voice.speak("Here's what I remember:")
                for f in facts:
                    print(f"    - {f}")
            else:
                voice.speak("I don't have any saved memories yet.")
            continue

        if lower.startswith("my name is "):
            name = user_input[len("my name is "):]
            info = memory.get("user_info", {})
            info["name"] = name
            memory.set("user_info", info)
            voice.speak(f"Nice to meet you, {name}. I'll remember that.")
            continue

        # Send to AI brain
        response = brain.think(user_input)

        # Check if the response contains an action
        action = try_parse_action(response)
        if action:
            # Speak the non-JSON part of the response
            clean_response = response.split("{")[0].strip()
            if clean_response:
                voice.speak(clean_response)
            result = execute_action(action)
            voice.speak(result)
        else:
            voice.speak(response)


def main():
    voice_mode = "--voice" in sys.argv
    try:
        run(voice_mode=voice_mode)
    except KeyboardInterrupt:
        print("\n\n  Jarvis shutting down. Goodbye.")


if __name__ == "__main__":
    main()
