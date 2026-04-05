"""Jarvis CLI entry point - run with: python -m jarvis"""

import sys
import readline  # enables arrow keys and history in input()

from jarvis.core.assistant import Jarvis
from jarvis.utils.formatting import (
    Colors, jarvis_prompt, user_prompt, format_response, format_header,
)


def main():
    assistant = Jarvis()

    print(f"{Colors.CYAN}{assistant.BANNER}{Colors.RESET}")
    print(format_header("Systems Online"))

    # Show initial status
    print(format_response(assistant.get_status()))
    print()
    print(format_response("How may I assist you today, sir?"))
    print(f"{Colors.DIM}  (Type 'help' for commands, 'quit' to exit){Colors.RESET}\n")

    while True:
        try:
            user_input = input(user_prompt())
        except (KeyboardInterrupt, EOFError):
            print(f"\n{format_response(assistant.chat('goodbye'))}")
            break

        if not user_input.strip():
            continue

        lower = user_input.strip().lower()
        if lower in ("quit", "exit", "bye", "goodbye", "shutdown"):
            print(format_response(assistant.chat("goodbye")))
            break

        if lower == "capabilities":
            print(format_response(assistant.list_capabilities()))
            continue

        response = assistant.chat(user_input)
        print(f"\n{jarvis_prompt()}{format_response(response)}\n")


if __name__ == "__main__":
    main()
