"""Common test fixtures for Nomos agent tests."""

from typing import List

import pytest
from pydantic import BaseModel

from nomos.config import AgentConfig, ToolsConfig
from nomos.core import Agent
from nomos.llms import LLMBase
from nomos.models.agent import (
    Action,
    Decision,
    DecisionExample,
    Message,
    Route,
    Step,
)
from nomos.models.tool import ToolWrapper
from nomos.tools.models import ArgDef, ToolDef
from nomos.utils.logging import log_error


class MockLLM(LLMBase):
    """Mock LLM for testing."""

    def __init__(self):
        """Initialize mock LLM."""
        self.responses = []
        self.messages_received = []
        self._generate_response = None

    def set_response(self, response: BaseModel, *, append: bool = False):
        """Set or queue a response that the mock LLM will return."""
        log_error(f"Setting mock response: {response}")
        if append:
            self.responses.append(response)
        else:
            self.responses = [response]

    def set_generate_response(self, response: str) -> None:
        """Set the response returned by ``generate``."""
        self._generate_response = response

    def generate(self, messages: List[Message], **kwargs: dict) -> str:
        """Return a preset string response and capture messages."""
        self.messages_received = messages
        if self._generate_response is None:
            raise ValueError("No generate response available")
        return self._generate_response

    def get_output(
        self, messages: List[Message], response_format: BaseModel, **kwargs: dict
    ) -> BaseModel:
        """Mock implementation that returns pre-set responses."""
        self.messages_received = messages

        if not self.responses:
            raise ValueError("No more mock response available")
        response = self.responses.pop(0)
        if not self.responses:
            self.responses.append(response)
        # Check if the response schema matches the expected format schema
        assert response.model_json_schema() == response_format.model_json_schema(), (
            f"Response schema mismatch: {response.model_json_schema()} != {response_format.model_json_schema()}"
        )
        return response

    def embed_text(self, text: str) -> List[float]:
        """Return a simple letter frequency embedding for the given text."""
        vector = [0.0] * 26
        for ch in text.lower():
            if "a" <= ch <= "z":
                vector[ord(ch) - 97] += 1.0
        return vector

    def embed_batch(self, texts: List[str]) -> List[List[float]]:
        """Embed a batch of texts using ``embed_text``."""
        return [self.embed_text(t) for t in texts]


@pytest.fixture
def mock_llm():
    """Fixture providing a mock LLM instance."""
    return MockLLM()


@pytest.fixture
def basic_steps():
    """Fixture providing basic steps for testing."""
    start_step = Step(
        step_id="start",
        description="Start step",
        routes=[Route(target="end", condition="User is done")],
        available_tools=["test_tool", "another_test_tool", "combinations"],
    )

    end_step = Step(step_id="end", description="End step", routes=[], available_tools=[])

    return [start_step, end_step]


@pytest.fixture
def mcp_server_url():
    """MCP Server URL"""
    return "https://gitmcp.io/dowhiledev/nomos"


@pytest.fixture
def mcp_server_name():
    """MCP Server name"""
    return "mcp_server"


@pytest.fixture
def steps_with_diferred_tools(mcp_server_name):
    """Fixture providing steps with a diferred tool."""
    start_step = Step(
        step_id="start",
        description="Start step",
        routes=[Route(target="end", condition="User is done")],
        available_tools=[f"@mcp/{mcp_server_name}"],
    )

    end_step = Step(step_id="end", description="End step", routes=[], available_tools=[])

    return [start_step, end_step]


@pytest.fixture
def test_tool_0():
    """Fixture providing a test tool function."""

    def test_tool(arg0: str = "test") -> str:
        """Test tool function."""
        return f"Test tool 0 response: {arg0}"

    return test_tool


@pytest.fixture
def test_tool_1():
    """Fixture providing a second test tool function."""

    def another_test_tool(arg1: str = "test") -> str:
        """Test tool function."""
        return f"Test tool 1 response: {arg1}"

    return another_test_tool


@pytest.fixture
def pkg_tool():
    """Fixture providing a package tool wrapper."""
    return ToolWrapper(
        tool_type="pkg",
        name="combinations",
        tool_identifier="itertools.combinations",
    )


@pytest.fixture
def mcp_tool(mcp_server_url, mcp_server_name):
    """Fixture providing a MCP tool wrapper."""
    return ToolWrapper(
        tool_type="mcp",
        name=mcp_server_name,
        tool_identifier=mcp_server_url,
    )


@pytest.fixture
def tool_defs():
    """Fixture providing tool definitions for testing."""
    return {
        "combinations": ToolDef(
            desc="Test tool for combinations",
            args=[
                ArgDef(key="iterable", type="List", desc="Input iterable"),
                ArgDef(key="r", type="int", desc="Length of combinations"),
            ],
        )
    }


@pytest.fixture
def basic_agent(mock_llm, basic_steps, test_tool_0, test_tool_1, pkg_tool, tool_defs):
    """Fixture providing a basic Nomos agent instance."""
    config = AgentConfig(
        name="test_agent",
        persona="Test persona",
        steps=basic_steps,
        start_step_id="start",
        tools=ToolsConfig(tool_defs=tool_defs),
    )
    return Agent.from_config(
        config=config, llm=mock_llm, tools=[test_tool_0, test_tool_1, pkg_tool]
    )


@pytest.fixture
def example_steps():
    """Steps including decision examples for testing."""
    example_decision = Decision(
        reasoning=["example"],
        action=Action.RESPOND.value,
        response="Example time",
    )

    start_step = Step(
        step_id="start",
        description="Start with examples",
        routes=[Route(target="end", condition="done")],
        available_tools=["test_tool"],
        examples=[
            DecisionExample(
                context="time question",
                decision=example_decision,
                visibility="always",
            ),
            DecisionExample(
                context="sqrt 4",
                decision="Use sqrt tool",
                visibility="dynamic",
            ),
        ],
    )

    end_step = Step(step_id="end", description="End")
    return [start_step, end_step]


@pytest.fixture
def example_agent(mock_llm, example_steps, test_tool_0, tool_defs):
    """Agent instance with steps that include examples."""
    config = AgentConfig(
        name="example_agent",
        persona="Example persona",
        steps=example_steps,
        start_step_id="start",
        max_examples=2,
        tools=ToolsConfig(tool_defs=tool_defs),
    )
    return Agent.from_config(config=config, llm=mock_llm, tools=[test_tool_0])


@pytest.fixture
def mcp_agent(mock_llm, steps_with_diferred_tools, mcp_tool):
    """Agent instance with MCP tool."""
    config = AgentConfig(
        name="test_agent",
        persona="Test persona",
        steps=steps_with_diferred_tools,
        start_step_id="start",
        tools=ToolsConfig(tool_defs={}),
    )
    return Agent.from_config(config=config, llm=mock_llm, tools=[mcp_tool])
