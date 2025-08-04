"""Logging utilities for Nomos."""

import os
import sys
from functools import lru_cache
from logging import Logger

from loguru import logger
from rich.console import Console
from rich.panel import Panel

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
    """Print the response from a Nomos session using rich panels."""
    console = Console()
    decision = response.decision
    tool_output = response.tool_output

    # Thoughts panel
    thoughts = "\n".join(decision.reasoning)
    console.print(Panel(thoughts, title="Thoughts", style="yellow", expand=False))

    # Action panels
    if decision.action == Action.RESPOND:
        action_response = (
            str(decision.response)[:97] + "..."
            if len(str(decision.response)) > 100
            else str(decision.response)
        )
        content = f"[bold blue]Responding Back:[/bold blue] {action_response}"
        if decision.suggestions:
            content += f"\n[dim]Suggestions: {', '.join(decision.suggestions)}[/dim]"
        console.print(Panel(content, style="blue", expand=False))

    elif decision.action == Action.TOOL_CALL and decision.tool_call:
        tool_args = decision.tool_call.tool_kwargs.model_dump_json()
        if len(tool_args) > 100:
            tool_args = tool_args[:97] + "..."
        content = (
            f"[bold magenta]Running Tool:[/bold magenta]\n"
            f"Tool: [bold]{decision.tool_call.tool_name}[/bold]\n"
            f"Args: {tool_args}"
        )
        console.print(Panel(content, style="magenta", expand=False))

    elif decision.action == Action.MOVE:
        content = f"[bold cyan]Moving to Next Step:[/bold cyan] {decision.step_id}"
        console.print(Panel(content, style="cyan", expand=False))

    elif decision.action == Action.END:
        content = "[bold red]Ending Session:[/bold red]\n"
        if decision.response:
            content += f"Final Response: {decision.response}"
        else:
            content += "Session completed successfully"
        console.print(Panel(content, style="red", expand=False))

    # Tool output panel
    if tool_output is not None:
        tool_output_str = str(tool_output)
        if len(tool_output_str) > 300:
            tool_output_str = tool_output_str[:297] + "..."
        console.print(Panel(tool_output_str, title="Tool Output", style="green", expand=False))
