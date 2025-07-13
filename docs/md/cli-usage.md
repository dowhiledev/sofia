# CLI Usage Guide

The Nomos CLI provides powerful commands to bootstrap, develop, and deploy your agents.

## Commands Overview

- [`nomos init`](#initialize-a-new-agent) - Create a new agent project
- [`nomos run`](#development-mode) - Run agent in development mode
- [`nomos train`](#training-mode) - Interactively refine agent decisions
- [`nomos serve`](#production-deployment) - Deploy agent with Docker
- [`nomos test`](#testing) - Run agent tests
- [`nomos validate`](#validate-configuration) - Validate agent configuration
- [`nomos schema`](#generate-yaml-schema) - Export JSON schema for your config
- `nomos --version` - Display CLI version

### Check Version and Help

```bash
nomos --version
nomos --help
```

## Initialize a New Agent

Create a new agent project interactively:

```bash
nomos init
```

### Options

- `--directory, -d`: Project directory (default: `./my-nomos-agent`)
- `--name, -n`: Agent name
- `--template, -t`: Template to use (`basic`, `conversational`, `workflow`)
- `--generate, -g`: Generate agent configuration using AI
- `--usecase, -u`: Use case description or path to text file (for AI generation)
- `--tools`: Comma-separated list of available tools (for AI generation)

### Examples

```bash
# Basic interactive setup
nomos init

# With specific directory and template
nomos init --directory ./my-bot --name chatbot --template basic

# Generate using AI with use case
nomos init --generate --usecase "Create a weather agent" --tools "weather_api"
```

This will interactively guide you to create a config YAML and starter Python file for your agent.

## Development Mode

Run your agent locally for development and testing:

```bash
nomos run
```

### Options

- `--config, -c`: Configuration file path (default: `config.agent.yaml`)
- `--tools, -t`: Python files with tool definitions (can be used multiple times) - **Note: As of v0.2.4, you can now specify tools directly in your agent config file**
- `--port, -p`: Development server port (default: `8000`)
- `--verbose, -v`: Enable verbose logging

### Examples

```bash
# Basic usage (tools will be loaded from config file)
nomos run

# With custom config and tools
nomos run --config my-config.yaml --tools tools.py --tools utils.py

# With verbose logging on custom port
nomos run --verbose --port 3000
```

## Training Mode

Run the agent interactively and record new decision examples:

```bash
nomos train
```

During training, the CLI shows each step ID and tool result. If you're not satisfied with the response, you can provide feedback which will be stored as an example for the current step.

## Production Deployment

Serve your agent using FastAPI and uvicorn for production:

```bash
nomos serve
```

### Options

- `--config, -c`: Configuration file path (default: `config.agent.yaml`)
- `--tools, -t`: Python files with tool definitions (can be used multiple times)
- `--port, -p`: Port to bind the server (if not specified, uses config or default)
- `--workers, -w`: Number of uvicorn workers

### Examples

```bash
# Basic deployment
nomos serve

# With custom config and tools
nomos serve --config my-config.yaml --tools tools.py

# Custom port and workers
nomos serve --port 9000 --workers 4

# Load tools from multiple files
nomos serve --tools tools.py --tools utils.py
```

## Testing

Run tests for your agent:

```bash
nomos test
```

### Options

- `--config, -c`: Path to `tests.agent.yaml` file (defaults to `tests.agent.yaml` in the current directory)
- `--coverage/--no-coverage`: Generate coverage report (default: `true`)
- Any additional arguments are passed directly to `pytest`.

### Examples

```bash
# Run all tests
nomos test

# Provide custom yaml file and verbose output
nomos test --config ./my_tests.yaml -v

# Pass any pytest args
nomos test tests/test_cli.py -k serve
```

## Agent Testing and Evaluation

Nomos provides comprehensive testing utilities to validate your agent's responses and simulate conversations.

### Smart Assertions

Use `smart_assert` to validate agent responses using LLM-based evaluation:

```python
from nomos.testing import smart_assert
from nomos import State, Summary, StepIdentifier
from nomos.models.agent import Message

def test_greeting(agent):
    context = State(
        history=[
            Summary(content="Initial summary"),
            Message(role="user", content="Hello"),
            StepIdentifier(step_id="start"),
        ]
    )
    res = agent.next("Hello", context.model_dump(mode="json"))
    smart_assert(res.decision, "Agent should greet the user", agent.llm)
```

### Scenario Testing

For multi-turn conversations, use `ScenarioRunner`:

```python
from nomos.testing.e2e import ScenarioRunner, Scenario

def test_budget_flow(agent):
    ScenarioRunner.run(
        agent,
        Scenario(
            scenario="User asks for budgeting advice",
            expectation="Agent explains how to plan a budget",
        ),
    )
```

### YAML Test Configuration

You can define agent tests in a YAML file and run them with `nomos test`.
Nomos looks for `tests.agent.yaml` by default.

```yaml
llm:
  provider: openai
  model: gpt-4o-mini

unit:
  greet:
    input: "Hello"
    expectation: "Greets the user"

e2e:
  budget_flow:
    scenario: "User asks for budgeting advice"
    expectation: "Agent explains how to plan a budget"
```

## Generate YAML Schema

Export the JSON schema for `config.agent.yaml` to enable editor validation and autocompletion:

```bash
nomos schema --output agent.schema.json
```

Reference the schema in your YAML file (works with VS Code YAML extension):

```yaml
# yaml-language-server: $schema=./agent.schema.json
```

## Validate Configuration

Validate your agent configuration file for syntax errors and best practices:

```bash
nomos validate config.agent.yaml
```

### Options

- `--verbose, -v`: Show detailed validation information including configuration details and warnings

### Examples

```bash
# Basic validation
nomos validate config.agent.yaml

# Detailed validation with recommendations
nomos validate config.agent.yaml --verbose

# Validate custom config file
nomos validate my-custom-config.yaml -v
```

The validate command checks for:

- **Syntax Errors**: YAML syntax and required fields
- **Configuration Issues**: Missing steps, unreachable steps, invalid references
- **Best Practices**: Recommendations for optimal agent configuration
- **Field Compatibility**: Supports both new and legacy field naming conventions

### Validation Output

```bash
✓ Configuration is valid!

Warnings:
• No LLM configuration specified - will use default OpenAI settings

Recommendations:
• Consider adding a persona to give your agent more character
```
