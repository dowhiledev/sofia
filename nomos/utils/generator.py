"""Agent configuration generator for Nomos."""

from typing import Optional

import yaml
from pydantic import BaseModel, Field
from rich.console import Console
from rich.prompt import Confirm, Prompt

from ..llms import LLMConfig
from ..models.agent import Message, Route
from ..models.agent import Step as AgentStep

REASONING_PROMPT = """
You are an expert agent configuration generator. Agent contains a set of steps and flows that the agent can take to achieve a specific goal.
Each step has a unique ID, a description, tools it can use, and routes to other steps.
You will be given a use case and a list of available tools (if any).

Your task is to identify the steps we need to cover all the cases in the usecase, identify which step should be routed to which step, and which tools should be available in each step.
You will generate a plan that includes the steps, their IDs, descriptions, available tools, and routes. Think step by step and do not rush.
"""

AGENT_CONFIG_GENERATION_PROMPT = """
You are an expert agent configuration generator. You will be given a use case and a list of available tools (if any).
Your task is to generate a valid agent configuration based on the provided use case and tools and the plan
"""


class Step(BaseModel):
    """Represents a step in the agent's workflow."""

    step_id: str = Field(..., description="Unique identifier for the step")
    description: str = Field(..., description="Description of what this step does")
    routes: list[Route] = Field(
        default_factory=list,
        description="List of routes that can be taken from this step",
    )
    available_tools: list[str] = Field(
        default_factory=list,
        description="List of tools available to the agent in this step (Only choose from the given tools)",
    )
    auto_flow: bool = Field(
        default=False,
        description="Flag indicating a step in a workflow where agent should not require user input to continue",
    )

    def to_agent_step(self) -> AgentStep:
        """Convert this Step to an AgentStep."""
        return AgentStep(
            step_id=self.step_id,
            description=self.description,
            routes=self.routes,
            available_tools=self.available_tools,
            auto_flow=self.auto_flow,
        )


class AgentConfiguration(BaseModel):
    """Configuration for the agent."""

    name: str = Field(..., description="Name of the agent (eg. 'example_agent')")
    persona: str = Field(..., description="Description of the agent's purpose and high-level goals")
    steps: list[Step] = Field(default_factory=list, description="")
    start_step_id: Optional[str] = Field(
        default=None,
        description="ID of the step to start with. If not provided, the first step will be used.",
    )

    def to_agent_steps(self) -> list[AgentStep]:
        """Convert all steps to AgentStep objects."""
        return [step.to_agent_step() for step in self.steps]

    def dump(self, filename: str) -> None:
        """Save the agent configuration to a YAML file."""
        with open(filename, "w") as file:
            yaml.dump(
                self.model_dump(mode="json"),
                file,
                default_flow_style=False,
                sort_keys=False,
            )


class AgentGenerator:
    """Generates agent configurations based on use cases and available tools."""

    def __init__(
        self,
        console: Optional[Console] = None,
        max_retries: int = 3,
        llm_config: Optional[LLMConfig] = None,
    ) -> None:
        """
        Initialize the AgentGenerator with an LLM configuration and console.

        :param console: Optional Rich Console for output.
        :param max_retries: Maximum number of retries for generating a valid agent configuration.
        :param llm_config: Optional LLM configuration. If not provided, defaults to OpenAI's GPT-4o-mini.
        """
        llm_config = llm_config or LLMConfig(provider="openai", model="gpt-4o-mini")
        self.llm = llm_config.get_llm()
        self.max_retries = max_retries
        self.console = console or Console()

    @staticmethod
    def validate_agent_configuration(config: AgentConfiguration) -> Optional[str]:
        """Validate the agent configuration."""
        errors = []
        available_steps = [step.step_id for step in config.steps]
        if config.start_step_id not in available_steps:
            errors.append(
                f" - Start step ID '{config.start_step_id}' is not valid. It must be one of the defined steps."
            )
        for step in config.steps:
            for route in step.routes:
                if route.target not in available_steps:
                    errors.append(
                        f"- Route in step '{step.step_id}' points to an invalid target step ID '{route.target}'."
                    )
        return "\n".join(errors) if errors else None

    def generate(self, usecase: str, tools_available: Optional[str] = None) -> AgentConfiguration:
        """
        Generate a basic agent configuration based on the use case.

        :param usecase: The use case for which the agent is being generated.
        :param tools_available: Optional string listing available tools for the agent.
        :return: An AgentConfiguration object containing the generated agent configuration.
        """
        usecase_str = f"Usecase: {usecase}"
        if tools_available:
            usecase_str += f"\nTools available: {tools_available}"

        messages = [
            Message(role="system", content=REASONING_PROMPT.strip()),
            Message(
                role="user",
                content=usecase_str,
            ),
        ]
        init_plan = self.llm.generate(messages)
        messages.append(Message(role="assistant", content=init_plan))
        self.console.print(f"Initial Plan for the given Usecase:\n{init_plan}")

        updated_plan = init_plan
        satisfied = False
        while not satisfied:
            satisfied = Confirm.ask("Are you Satisfied with this plan?")
            if satisfied:
                break
            needed_changes = Prompt.ask("What are the Changes you would like to make?")
            messages.append(
                Message(
                    role="user",
                    content=f"Make the Following Changes:\n{needed_changes}",
                )
            )
            updated_plan = self.llm.generate(messages)
            self.console.print(f"Updated Plan:\n{updated_plan}")

        _retries = 0
        messages = [
            Message(role="system", content=AGENT_CONFIG_GENERATION_PROMPT.strip()),
            Message(
                role="user",
                content=f"{usecase_str}\nConfiguration Plan: {updated_plan}",
            ),
        ]
        last_response: Optional[AgentConfiguration] = None
        while _retries < self.max_retries:
            response = self.llm.get_output(messages=messages, response_format=AgentConfiguration)
            errors = self.validate_agent_configuration(response)
            if not errors:
                last_response = response
                break
            messages.append(
                Message(
                    role="assistant",
                    content=response.model_dump_json() if response else "",
                )
            )
            messages.append(
                Message(
                    role="user",
                    content=f"Errors found in the configuration:\n{errors}\nPlease fix them.",
                )
            )
            _retries += 1
        if not last_response:
            self.console.print(
                "Failed to generate a valid agent configuration after multiple attempts."
            )
        assert isinstance(last_response, AgentConfiguration), (
            "Response is not of type AgentConfiguration"
        )
        return last_response


__all__ = ["AgentConfiguration", "AgentGenerator"]
