"""Common test fixtures for Nomos agent tests."""

import pytest
from typing import List
from pydantic import BaseModel
import pytest

from nomos.models.agent import Message, Step, Route
from nomos.llms import LLMBase
from nomos.core import Agent
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
        assert (
            response.model_json_schema() == response_format.model_json_schema()
        ), f"Response schema mismatch: {response.model_json_schema()} != {response_format.model_json_schema()}"
        return response


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
        available_tools=["test_tool", "another_test_tool", "itertools:combinations"],
    )

    end_step = Step(
        step_id="end", description="End step", routes=[], available_tools=[]
    )

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
def basic_agent(mock_llm, basic_steps, test_tool_0, test_tool_1):
    """Fixture providing a basic Nomos agent instance."""
    return Agent(
        name="test_agent",
        llm=mock_llm,
        steps=basic_steps,
        start_step_id="start",
        tools=[test_tool_0, test_tool_1],
        persona="Test persona",
    )
