"""Command Line Interface for Nomos."""

import os
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import List, Optional

import typer
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Confirm, Prompt
from rich.table import Table
from rich.text import Text

from . import __version__
from .config import AgentConfig, LoggingConfig, LoggingHandler
from .constants import (
    ERROR_COLOR,
    LLM_CHOICES,
    PRIMARY_COLOR,
    SUCCESS_COLOR,
    TEMPLATES,
    WARNING_COLOR,
)
from .core import Agent
from .llms import LLMConfig, OpenAI
from .models.agent import Action, DecisionExample, Step
from .server import run_server
from .utils.generator import AgentConfiguration, AgentGenerator

console = Console()
app = typer.Typer(
    name="nomos",
    help="Nomos CLI - Build Agents you can audit.",
    add_completion=True,
)


def _version_callback(value: bool) -> None:
    """Show version and exit."""
    if value:
        console.print(__version__)
        raise typer.Exit()


@app.callback()
def cli_app(
    version: Optional[bool] = typer.Option(
        None,
        "--version",
        "-v",
        help="Show Nomos version and exit",
        callback=_version_callback,
        is_eager=True,
    ),
) -> None:
    """Nomos CLI."""
    pass


banner_text = r"""
 __  _  __  __ __  __    __
|  \| |/__\|  V  |/__\ /' _/
| | ' | \/ | \_/ | \/ |`._`.
|_|\__|\__/|_| |_|\__/ |___/

Build Agents you can audit.
"""


def print_banner() -> None:
    """Print the Nomos banner."""
    banner = Panel(
        Text.from_markup(banner_text.strip(), justify="center"),
        border_style=PRIMARY_COLOR,
        title_align="left",
        padding=(1, 2),
        expand=False,
    )
    console.print()
    console.print(banner)
    console.print()


@app.command()
def init(
    directory: Optional[str] = typer.Option(
        None, "--directory", "-d", help="Directory to create the agent project in"
    ),
    name: Optional[str] = typer.Option(None, "--name", "-n", help="Name of the agent"),
    template: Optional[str] = typer.Option(
        None,
        "--template",
        "-t",
        help="Template to use (basic, conversational, workflow)",
    ),
    generate: bool = typer.Option(
        False, "--generate", "-g", help="Generate agent configuration using AI"
    ),
    usecase: Optional[str] = typer.Option(
        None, "--usecase", "-u", help="Use case description or path to text file"
    ),
    tools: Optional[str] = typer.Option(
        None, "--tools", help="Comma-separated list of available tools"
    ),
) -> None:
    r"""Initialize a new Nomos agent project interactively.

    Examples:\n
    # Traditional interactive setup\n
    nomos init\n
    # AI-powered generation from use case\n
    nomos init --generate --usecase "Create a weather agent" --tools "weather_api, calculator"\n
    # Load use case from file\n
    nomos init --generate --usecase "./my_usecase.txt"
    """
    print_banner()

    console.print(
        Panel(
            "Welcome to Nomos! Let's create your new agent project.",
            title="Project Initialization",
            border_style=PRIMARY_COLOR,
            title_align="left",
            padding=(1, 2),
            expand=False,
        )
    )

    # Get target directory
    if not directory:
        directory = Prompt.ask(
            "[bold cyan]Project directory[/bold cyan]", default="./my-nomos-agent"
        )

    target_dir = Path(directory).resolve()  # type: ignore

    if target_dir.exists() and any(target_dir.iterdir()):  # noqa
        if not Confirm.ask(
            f"Directory [bold]{target_dir}[/bold] already exists and is not empty. Continue?"
        ):
            console.print("[red]ERROR:[/red] Project initialization cancelled.", style=ERROR_COLOR)
            raise typer.Exit(1)

    target_dir.mkdir(parents=True, exist_ok=True)

    name = None
    persona = None
    steps: List[Step] = []

    # Choose LLM provider
    llm_table = Table(title="Choose LLM Provider")
    llm_table.add_column("Option", style=PRIMARY_COLOR)
    llm_table.add_column("Provider")

    for i, choice in enumerate(LLM_CHOICES.keys(), 1):
        llm_table.add_row(str(i), choice)

    console.print(llm_table)

    llm_choice_idx = (
        int(
            Prompt.ask(
                "[bold blue]Select LLM provider[/bold blue]",
                choices=[str(i) for i in range(1, len(LLM_CHOICES) + 1)],
                default="1",
            )
        )
        - 1
    )
    llm_choice = list(LLM_CHOICES.keys())[llm_choice_idx]

    if not generate and not template:
        generate = Confirm.ask(
            "[bold green]Would you like to generate the agent configuration using AI?[/bold green]",
            default=False,
        )

    if not generate and not template:
        template = Prompt.ask(
            "Please select a template for your agent",
            choices=list(TEMPLATES.keys()),
            default="basic",
        )

    if template:
        # Load template configuration
        template_config = TEMPLATES.get(template)
        if not template_config:
            console.print(
                f"[red]ERROR:[/red] Template '{template}' not found. Available templates: {', '.join(TEMPLATES.keys())}",
                style=ERROR_COLOR,
            )
            raise typer.Exit(1)
        name = template_config.get("name", "my_nomos_agent")  # type: ignore
        persona = template_config.get("persona", "A Nomos agent")  # type: ignore
        steps = template_config.get("steps", [])  # type: ignore

    if generate:
        llm_choice_idx = (
            int(
                Prompt.ask(
                    "[bold blue]Select LLM provider[/bold blue]",
                    choices=[str(i) for i in range(1, len(LLM_CHOICES) + 1)],
                    default="1",
                )
            )
            - 1
        )
        _llm_choice = LLM_CHOICES[list(LLM_CHOICES.keys())[llm_choice_idx]]
        _provider = _llm_choice["provider"]
        _model = Prompt.ask(
            "Mention the model you would like to use for generation",
            default=_llm_choice["model"],
        )
        usecase = Prompt.ask(
            "Please provide a use case description or path to a text file containing the use case",
            default="Create a weather agent",
        )
        tools = Prompt.ask(
            "Mention the tools available for the agent (comma-separated, e.g. weather_api, calculator)",
            default=None,
        )
        try:
            generated_config = _handle_config_generation(
                usecase=usecase,
                provider=_provider,
                model=_model,
                tools=tools,  # type: ignore
            )
            steps = generated_config.to_agent_steps()
            name = generated_config.name
            persona = generated_config.persona
        except Exception as e:
            console.print(
                f"[red]ERROR:[/red] Failed to generate agent configuration: {e}.",
                style=ERROR_COLOR,
            )

    # Generate project files
    _generate_project_files(target_dir, name, persona, llm_choice, steps)  # type: ignore

    console.print(
        Panel(
            f"[bold green]SUCCESS:[/bold green] Project created successfully in [bold]{target_dir}[/bold]",
            border_style=SUCCESS_COLOR,
            padding=(1, 2),
            expand=False,
        )
    )

    # Show next steps in a nicely formatted panel
    next_steps_content = f"""[bold cyan]1. Navigate to your project:[/bold cyan]
   [bold]cd {target_dir}[/bold]

[bold cyan]2. Edit configuration:[/bold cyan]
   [bold]config.agent.yaml[/bold]

[bold cyan]3. Add tools:[/bold cyan]
   [bold]tools/[/bold] directory

[bold cyan]4. Run development mode:[/bold cyan]
   [bold]nomos run[/bold]

[bold cyan]5. Serve your agent:[/bold cyan]
   [bold]nomos serve[/bold]"""

    console.print(
        Panel(
            next_steps_content,
            title="[bold]Next Steps[/bold]",
            border_style=PRIMARY_COLOR,
            padding=(1, 2),
            expand=False,
        )
    )


@app.command()
def run(
    config: Optional[str] = typer.Option(
        "config.agent.yaml", "--config", "-c", help="Path to agent configuration file"
    ),
    tools: Optional[List[str]] = typer.Option(
        None,
        "--tools",
        "-t",
        help="Python files containing tool definitions (can be used multiple times)",
    ),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Enable verbose logging"),
) -> None:
    """Run the Nomos agent in development mode."""
    print_banner()

    config_path = Path(config)  # type: ignore

    # Validate config file exists
    if not config_path.exists():
        console.print(
            f"[red]ERROR:[/red] Configuration file not found: [bold]{config_path}[/bold]",
            style=ERROR_COLOR,
        )
        raise typer.Exit(1)

    tool_paths = []
    if tools:
        for tool_file in tools:
            tool_path = Path(tool_file)
            if not tool_path.exists():
                console.print(
                    f"[red]ERROR:[/red] Tool file not found: [bold]{tool_path}[/bold]",
                    style=ERROR_COLOR,
                )
                raise typer.Exit(1)
            tool_paths.append(tool_path)

    try:
        _run(config_path, tool_paths, verbose)
    except KeyboardInterrupt:
        console.print("\n[yellow]Development Run stopped.[/yellow]", style=WARNING_COLOR)
    except Exception as e:
        console.print(f"[red]ERROR:[/red] Error running development Run: {e}", style=ERROR_COLOR)
        raise typer.Exit(1)


@app.command()
def train(
    config: Optional[str] = typer.Option(
        "config.agent.yaml", "--config", "-c", help="Path to agent configuration file"
    ),
    tools: Optional[List[str]] = typer.Option(
        None,
        "--tools",
        "-t",
        help="Python files containing tool definitions (can be used multiple times)",
    ),
) -> None:
    """Run the Nomos agent in training mode."""
    print_banner()

    config_path = Path(config)  # type: ignore

    if not config_path.exists():
        console.print(
            f"[red]ERROR:[/red] Configuration file not found: [bold]{config_path}[/bold]",
            style=ERROR_COLOR,
        )
        raise typer.Exit(1)

    tool_paths: list[Path] = []
    if tools:
        for tool_file in tools:
            tool_path = Path(tool_file)
            if not tool_path.exists():
                console.print(
                    f"[red]ERROR:[/red] Tool file not found: [bold]{tool_path}[/bold]",
                    style=ERROR_COLOR,
                )
                raise typer.Exit(1)
            tool_paths.append(tool_path)

    try:
        _train(config_path, tool_paths)
    except KeyboardInterrupt:
        console.print("\n[yellow]Training stopped.[/yellow]", style=WARNING_COLOR)
    except Exception as e:
        console.print(f"[red]ERROR:[/red] Error during training: {e}", style=ERROR_COLOR)
        raise typer.Exit(1)


@app.command()
def serve(
    config: Optional[str] = typer.Option(
        "config.agent.yaml", "--config", "-c", help="Path to agent configuration file"
    ),
    tools: Optional[List[str]] = typer.Option(
        None,
        "--tools",
        "-t",
        help="Python files containing tool definitions (can be used multiple times)",
    ),
    port: Optional[int] = typer.Option(None, "--port", "-p", help="Port to bind the server"),
    workers: Optional[int] = typer.Option(
        None, "--workers", "-w", help="Number of uvicorn workers"
    ),
) -> None:
    """Serve the Nomos agent using FastAPI and Uvicorn."""
    print_banner()

    config_path = Path(config)  # type: ignore

    if not config_path.exists():
        console.print(
            f"[red]ERROR:[/red] Configuration file not found: [bold]{config_path}[/bold]",
            style=ERROR_COLOR,
        )
        raise typer.Exit(1)

    tool_paths: list[Path] = []
    if tools:
        for tool_file in tools:
            tool_path = Path(tool_file)
            if not tool_path.exists():
                console.print(
                    f"[red]ERROR:[/red] Tool file not found: [bold]{tool_path}[/bold]",
                    style=ERROR_COLOR,
                )
                raise typer.Exit(1)
            tool_paths.append(tool_path)

    console.print(
        Panel(
            f"[bold green]Starting server on port [bold]{port or 'config'}[/bold][/bold green]",
            title="Serve",
            border_style=PRIMARY_COLOR,
            title_align="left",
            padding=(1, 2),
            expand=False,
        )
    )

    tool_dirs: set[str] = set()
    for p in tool_paths:
        tool_dirs.add(str(p if p.is_dir() else p.parent))

    default_tool_dir = Path.cwd() / "tools"
    if not tool_dirs and default_tool_dir.exists():
        tool_dirs.add(str(default_tool_dir))

    if tool_dirs:
        os.environ["TOOLS_PATH"] = os.pathsep.join(tool_dirs)

    cfg = AgentConfig.from_yaml(str(config_path))
    run_port = port if port is not None else cfg.server.port
    worker_count = workers if workers is not None else cfg.server.workers

    run_server(config_path, port=run_port, workers=worker_count)


@app.command()
def test(
    config: Optional[str] = typer.Option(
        None,
        "--config",
        "-c",
        help="Path to YAML test configuration file (defaults to tests.agent.yaml)",
    ),
    coverage: bool = typer.Option(
        True, "--coverage/--no-coverage", help="Generate coverage report"
    ),
    pytest_args: List[str] = typer.Argument(None),
) -> None:
    """Run the Nomos testing framework."""
    print_banner()

    console.print(
        Panel(
            "[bold cyan]Running Nomos agent tests[/bold cyan]",
            title="Testing Framework",
            border_style=PRIMARY_COLOR,
            title_align="left",
            padding=(1, 2),
            expand=False,
        )
    )

    yaml_path = Path(config) if config else Path.cwd() / "tests.agent.yaml"

    try:
        if yaml_path.exists():
            from .testing.yaml_runner import run_yaml_tests

            result = run_yaml_tests(yaml_path, pytest_args, coverage)
            if result != 0:
                console.print("[red]Some tests failed![/red]", style=ERROR_COLOR)
                raise typer.Exit(result)
            console.print("[green]All tests passed![/green]", style=SUCCESS_COLOR)
        else:
            _run_tests(pytest_args, coverage)
    except Exception as e:
        console.print(f"[red]ERROR:[/red] Error running tests: {e}", style=ERROR_COLOR)
        raise typer.Exit(1)


@app.command()
def schema(
    output: Optional[str] = typer.Option(
        None,
        "--output",
        "-o",
        help="Write JSON schema to file instead of stdout",
    ),
) -> None:
    """Generate JSON schema for agent configuration."""
    import json

    schema = AgentConfig.model_json_schema()
    schema_json = json.dumps(schema, indent=2)
    if output:
        Path(output).write_text(schema_json)
        console.print(
            f"[green]SUCCESS:[/green] Schema written to [bold]{output}[/bold]",
            style=SUCCESS_COLOR,
        )
    else:
        console.print_json(schema_json)


@app.command()
def validate(
    config: str = typer.Argument(..., help="Path to agent configuration YAML file to validate"),
    verbose: bool = typer.Option(
        False, "--verbose", "-v", help="Show detailed validation information"
    ),
) -> None:
    """Validate agent configuration YAML file."""
    print_banner()

    config_path = Path(config)

    # Check if file exists
    if not config_path.exists():
        console.print(
            f"[red]ERROR:[/red] Configuration file not found: [bold]{config_path}[/bold]",
            style=ERROR_COLOR,
        )
        raise typer.Exit(1)

    # Check if file has correct extension
    if config_path.suffix.lower() not in [".yaml", ".yml"]:
        console.print(
            f"[yellow]WARNING:[/yellow] File extension is not .yaml or .yml: [bold]{config_path}[/bold]",
            style=WARNING_COLOR,
        )

    console.print(
        Panel(
            f"Validating configuration file: [bold]{config_path}[/bold]",
            title="Configuration Validation",
            border_style=PRIMARY_COLOR,
            title_align="left",
            padding=(1, 2),
            expand=False,
        )
    )

    try:
        # Attempt to load and validate the configuration
        agent_config = AgentConfig.from_yaml(str(config_path))

        # If we reach here, the configuration is valid
        console.print(
            Panel(
                "[bold green]✓ Configuration is valid![/bold green]",
                border_style=SUCCESS_COLOR,
                padding=(1, 2),
                expand=False,
            )
        )

        if verbose:
            # Show detailed information about the configuration
            info_table = Table(title="Configuration Details")
            info_table.add_column("Property", style=PRIMARY_COLOR)
            info_table.add_column("Value")

            info_table.add_row("Agent Name", agent_config.name)
            info_table.add_row("Persona", agent_config.persona or "Not specified")
            info_table.add_row("Number of Steps", str(len(agent_config.steps)))
            info_table.add_row("Start Step ID", agent_config.start_step_id)
            info_table.add_row("Max Iterations", str(agent_config.max_iter))
            info_table.add_row("Max Errors", str(agent_config.max_errors))
            info_table.add_row("Max Examples", str(agent_config.max_examples))

            if agent_config.llm:
                if isinstance(agent_config.llm, dict):
                    info_table.add_row("LLM", "Multiple LLMs configured")
                    for llm_id, llm_config in agent_config.llm.items():
                        info_table.add_row(llm_id)
                        info_table.add_row("⮑ Provider", llm_config.provider)
                        info_table.add_row("⮑ Model", llm_config.model)
                else:
                    info_table.add_row("LLM Provider", agent_config.llm.provider)
                    info_table.add_row("LLM Model", agent_config.llm.model)
            else:
                info_table.add_row("LLM", "Using default (OpenAI)")

            if agent_config.flows:
                info_table.add_row("Number of Flows", str(len(agent_config.flows)))

            if agent_config.session:
                info_table.add_row("Session Store Type", agent_config.session.store_type.value)
                info_table.add_row("Session TTL", f"{agent_config.session.default_ttl}s")

            info_table.add_row("Server Port", str(agent_config.server.port))
            info_table.add_row("Server Workers", str(agent_config.server.workers))

            console.print()
            console.print(info_table)

            # Show step details
            if agent_config.steps:
                steps_table = Table(title="Steps Overview")
                steps_table.add_column("Step ID", style=PRIMARY_COLOR)
                steps_table.add_column("Description")
                steps_table.add_column("Examples Count")

                for step in agent_config.steps:
                    example_count = len(step.examples) if step.examples else 0
                    steps_table.add_row(
                        step.step_id,
                        step.description[:50] + "..."
                        if len(step.description) > 50
                        else step.description,
                        str(example_count),
                    )

                console.print()
                console.print(steps_table)

        # Validation warnings and recommendations
        warnings = []
        recommendations = []

        # Check for common issues
        if not agent_config.persona:
            recommendations.append("Consider adding a persona to give your agent more character")

        if len(agent_config.steps) == 1:
            recommendations.append(
                "Single-step agents are simple - consider adding more steps for complex workflows"
            )

        if not agent_config.llm:
            warnings.append("No LLM configuration specified - will use default OpenAI settings")

        if agent_config.start_step_id not in [step.step_id for step in agent_config.steps]:
            warnings.append(
                f"Start step ID '{agent_config.start_step_id}' not found in defined steps"
            )

        # Check for unreachable steps
        referenced_steps = {agent_config.start_step_id}
        for step in agent_config.steps:
            if step.routes:
                for route in step.routes:
                    referenced_steps.add(route.target)

        unreachable_steps = [
            step.step_id for step in agent_config.steps if step.step_id not in referenced_steps
        ]
        if unreachable_steps:
            warnings.append(f"Potentially unreachable steps: {', '.join(unreachable_steps)}")

        # Display warnings and recommendations
        if warnings or recommendations:
            console.print()

        if warnings:
            warning_panel = Panel(
                "\n".join([f"• {warning}" for warning in warnings]),
                title="[bold yellow]Warnings[/bold yellow]",
                border_style=WARNING_COLOR,
                padding=(1, 2),
                expand=False,
            )
            console.print(warning_panel)

        if recommendations:
            recommendation_panel = Panel(
                "\n".join([f"• {rec}" for rec in recommendations]),
                title="[bold blue]Recommendations[/bold blue]",
                border_style=PRIMARY_COLOR,
                padding=(1, 2),
                expand=False,
            )
            console.print(recommendation_panel)

    except Exception as e:
        console.print(
            Panel(
                f"[bold red]✗ Configuration validation failed![/bold red]\n\nError: {str(e)}",
                border_style=ERROR_COLOR,
                padding=(1, 2),
                expand=False,
            )
        )

        if verbose:
            import traceback

            console.print("\n[red]Detailed error information:[/red]")
            console.print(traceback.format_exc())

        raise typer.Exit(1)


def _generate_project_files(
    target_dir: Path, name: str, persona: str, llm_choice: str, steps: List[Step]
) -> None:
    """Generate project files for the new agent."""
    # Generate config.agent.yaml
    assert len(steps) > 0, "At least one step must be defined for the agent."
    agent_config = AgentConfig(
        name=name,
        persona=persona,
        steps=steps,
        start_step_id=steps[0].step_id,
        llm=LLMConfig(
            provider=LLM_CHOICES[llm_choice]["provider"],
            model=LLM_CHOICES[llm_choice]["model"],
        ),
        logging=LoggingConfig(
            enable=True,
            handlers=[
                LoggingHandler(
                    type="stderr",
                    level="INFO",
                    format="{time:YYYY-MM-DD at HH:mm:ss} | {level} | {message}",
                )
            ],
        ),
    )
    agent_config.to_yaml(str(target_dir / "config.agent.yaml"))

    # Create tools directory
    tools_dir = target_dir / "tools"
    tools_dir.mkdir(exist_ok=True)

    tools_init_content = [
        '"""This module imports all tools from the tools directory and makes them available in a list."""',
        "",
        "import os",
        "",
        "tool_list: list = []",
        "",
        "for filename in os.listdir(os.path.dirname(__file__)):",
        "    if filename.endswith('.py') and filename != '__init__.py':",
        "        module_name = filename[:-3]  # Remove the .py extension",
        "        try:",
        "            module = __import__(f'tools.{module_name}', fromlist=[''])",
        "            tool_list.extend(getattr(module, 'tools', []))",
        "        except ImportError as e:",
        "            print(f'Warning: Could not import {module_name}: {e}')",
        "",
        "__all__ = ['tool_list']",
    ]
    sample_tool_content = [
        '"""Sample tools for the Nomos agent."""',
        "",
        "def sample_tool(query: str) -> str:",
        '    """',
        "    A sample tool that echoes the input query.",
        "",
        "    Args:",
        "        query: The input query to echo",
        "",
        "    Returns:",
        "        The echoed query with a prefix",
        '   """',
        "    return f'You said: {query}'",
        "",
        "def get_current_time() -> str:",
        '    """Get the current time as a string."""',
        "",
        "    from datetime import datetime",
        "    return datetime.now().isoformat()",
        "",
        "# Export tools for discovery",
        "tools = [sample_tool, get_current_time]",
    ]
    main_content = [
        '"""Main entry point for the Nomos agent."""',
        "",
        "import os",
        "import sys",
        "from pathlib import Path",
        "from dotenv import load_dotenv",
        "",
        "# Load environment variables from .env file if it exists",
        "env_file = Path(__file__).parent / '.env.local'",
        "if env_file.exists():",
        "    load_dotenv(dotenv_path=env_file)",
        "else:",
        "    print('WARNING: .env file not found. Environment variables will not be loaded.')",
        "",
        "# Add tools directory to Python path",
        "sys.path.insert(0, str(Path(__file__).parent))",
        "",
        "from nomos import *",
        "from tools import tool_list",
        "",
        "def main():",
        '    """Run the agent interactively."""',
        "    # Load configuration",
        "    config_path = Path(__file__).parent / 'config.agent.yaml'",
        "    config = AgentConfig.from_yaml(str(config_path))",
        "",
        "    # Create agent",
        "    agent = Agent.from_config(config, tools=tool_list)",
        "",
        "    # Create session",
        "    session = agent.create_session(verbose=True)",
        "",
        "    print(f\"Agent {config.name} is ready! Type 'quit' to exit.\\n\")",
        '    print(f"Available tools: {[tool.__name__ if callable(tool) else str(tool) for tool in tool_list]}\\n")',
        "",
        "    while True:"
        "        try:"
        "            user_input = input('You: ').strip()"
        "            if user_input.lower() in ['quit', 'exit', 'bye']:"
        "                print('Goodbye!')"
        "                break",
        "            if not user_input:                continue",
        "            res = session.next(user_input, verbose=True)",
        "            if hasattr(res.decision, 'response') and res.decision.response:",
        '                print(f"\nAgent {config.name}: {res.decision.response}")'
        "        except KeyboardInterrupt:"
        '            print("\\nGoodbye!")'
        "            break",
        "        except Exception as e:",
        '            print(f"ERROR: {e}")',
        "",
        "if __name__ == '__main__':",
        "    main()",
    ]
    requirements_content = [
        "nomos[cli,serve,traces] >=0.2.4",
        f"nomos[{LLM_CHOICES[llm_choice]['provider'].lower()}] >=0.2.4",
    ]
    env_content = [
        "# Environment variables for your Nomos agent",
        "",
        "# LLM API Keys (uncomment the one you're using)",
        "# OPENAI_API_KEY=your_openai_api_key_here",
        "# MISTRAL_API_KEY=your_mistral_api_key_here",
        "# GOOGLE_API_KEY=your_google_api_key_here",
        "",
        "# Server configuration",
        "PORT=8000",
        "",
        "# Optional: Database configuration for persistent sessions",
        "# DATABASE_URL=postgresql+asyncpg://user:password@localhost/dbname",
        "# REDIS_URL=redis://localhost:6379/0",
        "",
        "# Optional: Tracing configuration",
        "# ENABLE_TRACING=true",
        "# ELASTIC_APM_SERVER_URL=http://localhost:8200",
        "# ELASTIC_APM_TOKEN=your_apm_token",
        "# SERVICE_NAME=my-nomos-agent",
        "# SERVICE_VERSION=1.0.0",
        "",
    ]
    project_title = name.replace("_", " ").title() if name else "My Nomos Agent"
    readme_content = [
        f"# {project_title} Agent [![Nomos Badge](https://img.shields.io/badge/Powered%20By-NOMOS-brightgreen)](https://github.com/dowhiledev/nomos)",
        f"Persona: {persona}",
        "",
        "## Configuration",
        "Edit the `config.agent.yaml` file to customize your agent.",
        "",
        "## Tools",
        "Add your custom tools in the `tools/` directory.",
        "",
        "> [!NOTE]"
        "> Copy the `.env.example` file to `.env` using `cp .env.example .env.local` and fill in your environment variables.",
        "",
        "## Running the Agent",
        "Run the agent in development mode with:",
        "```bash",
        "nomos run",
        "```",
        "",
        "## Serving the Agent",
        "Serve the agent using Uvicorn with:",
        "```bash",
        "nomos serve",
        "```",
    ]

    # Write files
    agent_config.to_yaml(str(target_dir / "config.agent.yaml"))
    (target_dir / "tools" / "__init__.py").write_text("\n".join(tools_init_content))
    (target_dir / "tools" / "sample_tool.py").write_text("\n".join(sample_tool_content))
    (target_dir / "main.py").write_text("\n".join(main_content))
    (target_dir / "requirements.txt").write_text("\n".join(requirements_content))
    (target_dir / ".env").write_text("\n".join(env_content))
    (target_dir / "README.md").write_text("\n".join(readme_content))
    console.print(
        f"[green]SUCCESS:[/green] Project files generated in [bold]{target_dir}[/bold]",
        style=SUCCESS_COLOR,
    )


def _run(config_path: Path, tool_files: List[Path], verbose: bool) -> None:
    """Run the agent in development mode."""
    current_dir = Path.cwd()

    # Collect tool directories
    tool_dirs: set[str] = {str(p if p.is_dir() else p.parent) for p in tool_files}
    default_tool_dir = current_dir / "tools"
    if default_tool_dir.exists():
        tool_dirs.add(str(default_tool_dir))

    if tool_dirs:
        os.environ["TOOLS_PATH"] = os.pathsep.join(tool_dirs)
    env_file = current_dir / ".env.local"
    # Create development server script
    dev_server_code = [
        '"""Development server for Nomos agents."""',
        "",
        "import sys",
        "import os",
        "from pathlib import Path",
        f'if Path("{str(env_file)}").exists():',
        "    from dotenv import load_dotenv",
        f'    load_dotenv(dotenv_path="{str(env_file)}")',
        "else:",
        "    print('WARNING: .env file not found. Environment variables will not be loaded.')",
        "",
        "sys.path.insert(0, str(Path.cwd()))",
        "",
        "from nomos import *",
        "from nomos.api.tools import tool_list",
        "",
        "def main():",
        "    try:",
        f'        config = AgentConfig.from_yaml("{config_path}")',
        "        agent = Agent.from_config(config, tools=tool_list)",
        "        session = agent.create_session()",
        "",
        '        print(f"Agent {config.name} ready in interactive mode!")',
        f'        print(f"Config: {config_path}")',
        "        print('Type (quit, exit, bye) to exit\\n')",
        "",
        "        while True:",
        "            try:",
        "                user_input = input('You: ').strip()",
        "                if user_input.lower() in ['quit', 'exit', 'bye']:",
        "                    break",
        "                if not user_input:",
        "                    continue",
        f"                res = session.next(user_input, verbose={verbose})",
        "                print(f'Agent: {res.decision.response}')",
        "                print()",
        "                if res.decision.action == Action.END:",
        "                    print('Session ended.')",
        "                    break",
        "            except KeyboardInterrupt:",
        "                break",
        "            except Exception as e:",
        "                print(f'Error: {e}')",
        f"                if {verbose}:",
        "                    import traceback",
        "                    traceback.print_exc()",
        "                    break",
        "    except Exception as e:",
        "        print(f'ERROR: Failed to start agent: {e}')",
        f"        if {verbose}:",
        "            import traceback",
        "            traceback.print_exc()",
        "",
        "if __name__ == '__main__':",
        "    main()",
    ]

    with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as temp_script:
        temp_script_path = temp_script.name
        temp_script.write("\n".join(dev_server_code))

    try:
        console.print(f"[bold cyan]Working directory:[/bold cyan] {current_dir}")
        result = subprocess.run([sys.executable, temp_script_path], cwd=current_dir, check=False)
        if result.returncode not in (0, 130):
            console.print(
                f"[red]ERROR:[/red] Development server exited with code {result.returncode}",
                style=ERROR_COLOR,
            )
    finally:
        os.unlink(temp_script_path)


def _train(config_path: Path, tool_files: List[Path]) -> None:
    """Interactive training loop for refining agent decisions."""
    current_dir = Path.cwd()

    tool_dirs: set[str] = {str(p if p.is_dir() else p.parent) for p in tool_files}
    default_tool_dir = current_dir / "tools"
    if default_tool_dir.exists():
        tool_dirs.add(str(default_tool_dir))

    if tool_dirs:
        os.environ["TOOLS_PATH"] = os.pathsep.join(tool_dirs)
    else:
        console.print(
            "[yellow]WARNING:[/yellow] No tool files provided and no tools directory found. Running without tools.",
            style=WARNING_COLOR,
        )

    from nomos.api.tools import tool_list

    config = AgentConfig.from_yaml(str(config_path))
    agent = Agent.from_config(config, tools=tool_list)

    console.print(
        f"[bold cyan]Agent[/bold cyan] [bold]{config.name}[/bold] [cyan]loaded in training mode.[/cyan]",
        style=PRIMARY_COLOR,
    )
    console.print("Type quit to exit\n")

    session_data: Optional[dict] = None
    last_action: Action = Action.RESPOND
    while True:
        # print(session_data)
        if last_action == Action.RESPOND:
            user_input = Prompt.ask("You").strip()
            if user_input.lower() in {"quit", "exit", "bye"}:
                break
        else:
            user_input = None
        res = agent.next(user_input, session_data, return_step=True, return_tool=True)
        if res.decision.action == Action.RESPOND:
            console.print(
                "Agent:\nReasoning:{}\nResponse: {}".format(
                    "\n".join(res.decision.reasoning), res.decision.response
                ),
                style=PRIMARY_COLOR,
            )
        elif res.decision.action == Action.TOOL_CALL:
            console.print(
                "Agent:\nReasoning:{}\nTool call: {}\nTool Result: {}".format(
                    "\n".join(res.decision.reasoning),
                    res.decision.tool_call,
                    res.tool_output,
                ),
                style=PRIMARY_COLOR,
            )
        elif res.decision.action == Action.MOVE:
            console.print(
                "Agent:\nReasoning:{}\nMoving to step: {}".format(
                    "\n".join(res.decision.reasoning), res.decision.step_id
                ),
                style=PRIMARY_COLOR,
            )
        elif res.decision.action == Action.END:
            console.print(
                "Agent:\nReasoning:{}\nEnding session.".format("\n".join(res.decision.reasoning)),
                style=PRIMARY_COLOR,
            )
            break
        else:
            console.print(
                "Agent:\nReasoning:{}\nUnknown action: {}".format(
                    "\n".join(res.decision.reasoning), res.decision.action
                ),
                style=ERROR_COLOR,
            )

        if Confirm.ask("Are you satisfied with this decision?", default=True):
            last_action = res.decision.action
            continue

        feedback = Prompt.ask("What should have happened?")

        assert res.state is not None, "Session state is None. Cannot take step back."

        flow_memory_context = (
            res.state.flow_state.flow_memory_context if res.state.flow_state else None
        )
        llms = config.get_llm() or {}
        llm = llms.get("global") or OpenAI()
        context_summary = llm.generate_summary(
            flow_memory_context[:-1]
            if flow_memory_context and len(flow_memory_context) > 1
            else res.state.history[:-1]
            if len(res.state.history) > 1
            else []
        )

        for step in config.steps:
            if step.step_id == res.state.current_step_id:
                if step.examples is None:
                    step.examples = []
                step.examples.append(
                    DecisionExample(context=" ".join(context_summary.summary), decision=feedback)
                )
                break

        config.to_yaml(str(config_path))
        agent = Agent.from_config(config, tools=tool_list)
        console.print(
            f"[green]SUCCESS:[/green] Example added for step {res.state.current_step_id}. Agent reloaded."
        )


def _run_tests(pytest_args: Optional[List[str]] = None, coverage: bool = False) -> None:
    """Run tests using pytest."""
    cmd = ["python", "-m", "pytest"] + (pytest_args or ["."])

    if coverage:
        cmd.extend(["--cov=.", "--cov-report=term-missing"])

    console.print(
        f"Running tests with command: [bold]{' '.join(cmd)}[/bold]",
        style=PRIMARY_COLOR,
    )

    result = subprocess.run(cmd)

    if result.returncode == 0:
        console.print("[green]All tests passed![/green]", style=SUCCESS_COLOR)
    else:
        console.print("[red]Some tests failed![/red]", style=ERROR_COLOR)
        raise typer.Exit(result.returncode)


def _handle_config_generation(
    usecase: str,
    provider: Optional[str] = None,
    model: Optional[str] = None,
    tools: Optional[str] = None,
) -> AgentConfiguration:
    """Handle AI generation of agent configuration."""
    llm_config: Optional[LLMConfig] = None
    if provider or model:
        llm_config = LLMConfig(
            provider=provider,
            model=model,
        )
    generator = AgentGenerator(
        console=console,
        llm_config=llm_config,
    )
    return generator.generate(usecase=usecase, tools_available=tools)


def main() -> None:
    """Main CLI entry point."""
    app()


if __name__ == "__main__":
    main()
