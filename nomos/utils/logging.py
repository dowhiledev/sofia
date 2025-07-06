"""Logging utilities for Nomos."""

import os
import sys
from functools import lru_cache
from logging import Logger

import colorama
from colorama import Fore, Style
from loguru import logger

from ..models.agent import Action, Response


@lru_cache(maxsize=1)
def get_logger() -> Logger:
    """Get the configured logger."""
    LOG_LEVEL: str = os.getenv("NOMOS_LOG_LEVEL", "INFO").upper()
    ENABLE_LOGGING: bool = os.getenv("NOMOS_ENABLE_LOGGING", "false").lower() == "true"
    logger.remove()
    if ENABLE_LOGGING:
        config_dict = {
            "handlers": [
                {
                    "sink": sys.stdout,
                    "format": "{time:YYYY-MM-DD at HH:mm:ss} | {level} | {message}",
                    "level": LOG_LEVEL,
                },
            ],
        }
        logger.configure(**config_dict)
        logger.info(f"Logging is enabled. Log level set to {LOG_LEVEL}.")

    return logger


def log_debug(message: str) -> None:
    """Log a debug message."""
    logger = get_logger()
    logger.debug(message)


def log_info(message: str) -> None:
    """Log an info message."""
    logger = get_logger()
    logger.info(message)


def log_warning(message: str) -> None:
    """Log a warning message."""
    logger = get_logger()
    logger.warning(message)


def log_error(message: str) -> None:
    """Log an error message."""
    logger = get_logger()
    logger.error(message)


def pp_response(response: "Response") -> None:
    """Print the response from a Nomos session."""
    colorama.init(autoreset=True)

    decision = response.decision
    tool_output = response.tool_output

    print(f"\n{Style.BRIGHT}{Fore.YELLOW}Thoughts:{Style.RESET_ALL}")
    print("\n".join(decision.reasoning))

    # Format output based on action type
    if decision.action == Action.RESPOND:
        print(
            f"{Style.BRIGHT}{Fore.BLUE}Responding Back:{Style.RESET_ALL}",
            f"{decision.response}",
        )
        if decision.suggestions:
            print(f"{Style.DIM}Suggestions: {', '.join(decision.suggestions)}{Style.RESET_ALL}")

    elif decision.action == Action.TOOL_CALL and decision.tool_call:
        print(f"{Style.BRIGHT}{Fore.MAGENTA}Running Tool:{Style.RESET_ALL}")
        tool_args = decision.tool_call.tool_kwargs.model_dump_json()
        # Trim arguments if too long
        if len(tool_args) > 100:
            tool_args = tool_args[:97] + "..."
        print(f"Tool: {Style.BRIGHT}{decision.tool_call.tool_name}{Style.RESET_ALL}")
        print(f"Args: {tool_args}")

    elif decision.action == Action.MOVE:
        print(
            f"{Style.BRIGHT}{Fore.CYAN}Moving to Next Step:{Style.RESET_ALL}",
            decision.step_id,
        )

    elif decision.action == Action.END:
        print(f"{Style.BRIGHT}{Fore.RED}Ending Session:{Style.RESET_ALL}")
        if decision.response:
            print(f"Final Response: {decision.response}")
        else:
            print("Session completed successfully")

    # Show tool output if available
    if tool_output is not None:
        print(f"{Style.BRIGHT}{Fore.GREEN}Tool Output:{Style.RESET_ALL}")
        tool_output_str = str(tool_output)
        # Trim tool output if too long
        if len(tool_output_str) > 300:
            tool_output_str = tool_output_str[:297] + "..."
        print(tool_output_str)

    print()
