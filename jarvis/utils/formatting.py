"""Output formatting utilities for Jarvis."""


class Colors:
    CYAN = "\033[96m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    RED = "\033[91m"
    BLUE = "\033[94m"
    MAGENTA = "\033[95m"
    BOLD = "\033[1m"
    DIM = "\033[2m"
    RESET = "\033[0m"


def jarvis_prompt():
    return f"{Colors.CYAN}{Colors.BOLD}JARVIS>{Colors.RESET} "


def user_prompt():
    return f"{Colors.GREEN}{Colors.BOLD}You>{Colors.RESET} "


def format_response(text):
    return f"{Colors.CYAN}{text}{Colors.RESET}"


def format_error(text):
    return f"{Colors.RED}[ERROR] {text}{Colors.RESET}"


def format_warning(text):
    return f"{Colors.YELLOW}[WARNING] {text}{Colors.RESET}"


def format_success(text):
    return f"{Colors.GREEN}{text}{Colors.RESET}"


def format_header(text):
    width = 50
    return (
        f"\n{Colors.CYAN}{Colors.BOLD}"
        f"{'=' * width}\n"
        f"{text:^{width}}\n"
        f"{'=' * width}"
        f"{Colors.RESET}\n"
    )
