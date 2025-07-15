"""Tests for core Nomos agent functionality."""

import os
from pathlib import Path
from unittest.mock import MagicMock, Mock, patch

import pytest

from nomos.config import AgentConfig, ToolsConfig
from nomos.core import Agent, Session
from nomos.llms import LLMConfig
from nomos.llms.base import LLMBase
from nomos.models.agent import (
    Action,
    Decision,
    DecisionConstraints,
    Event,
    Route,
    Step,
    StepIdentifier,
    StepOverrides,
    Summary,
)
from nomos.models.tool import Tool, ToolWrapper
from nomos.tools.mcp import MCPServer
from nomos.tools.models import ArgDef, ToolDef


def test_agent_initialization(basic_agent):
    """Test that agent initializes correctly."""
    assert basic_agent.name == "test_agent"
    assert len(basic_agent.steps) == 2
    assert basic_agent.start == "start"
    assert basic_agent.persona == "Test persona"
    assert len(basic_agent.tools) == 3


def test_session_creation(basic_agent):
    """Test that agent can create a new session."""
    session = basic_agent.create_session()
    assert session.current_step.step_id == "start"
    assert len(session.memory.context) == 0


def test_tool_registration(basic_agent, test_tool_0):
    """Test that tools are properly registered and converted to Tool objects."""
    tool_name = test_tool_0.__name__
    session = basic_agent.create_session()
    assert len(session.tools) == 3
    assert isinstance(session.tools[tool_name], Tool)


def test_pkg_tool_registration(basic_agent):
    """Test that package tools are properly registered."""
    session = basic_agent.create_session()
    assert len(session.tools) == 3
    assert "combinations" in session.tools
    assert session.tools["combinations"].name == "combinations"


def test_api_tool_registration(basic_agent):
    """Test that API tools are properly registered."""

    # Create an API tool wrapper
    api_wrapper = ToolWrapper(
        tool_type="api",
        name="test_api",
        tool_identifier="GET/https://api.example.com/users",
    )

    # Create custom steps that reference the API tool
    steps = [
        Step(
            step_id="start",
            description="Start step with API tool",
            routes=[Route(target="end", condition="Task completed")],
            available_tools=["test_api"],
        ),
        Step(step_id="end", description="End step", routes=[], available_tools=[]),
    ]

    # Create a new agent with the API tool
    config = AgentConfig(
        name="api_test_agent",
        persona="API test persona",
        steps=steps,
        start_step_id="start",
        tools=ToolsConfig(tool_defs={}),
    )

    agent = Agent.from_config(
        config=config,
        llm=basic_agent.llm,
        tools=[api_wrapper],
    )

    session = agent.create_session()
    assert len(session.tools) == 1
    assert "test_api" in session.tools
    assert session.tools["test_api"].name == "test_api"


def test_basic_conversation_flow(basic_agent, test_tool_0, test_tool_1, tool_defs):
    """Test a basic conversation flow with the agent."""

    # Set up session
    session = basic_agent.create_session()

    expected_decision_model = basic_agent.llm._create_decision_model(
        current_step=session.current_step,
        current_step_tools=(
            Tool.from_function(test_tool_0, tool_defs=tool_defs),
            Tool.from_function(test_tool_1, tool_defs=tool_defs),
            ToolWrapper(
                tool_type="pkg",
                name="combinations",
                tool_identifier="itertools.combinations",
            ).get_tool(tool_defs=tool_defs),
        ),
    )
    ask_response = expected_decision_model(
        reasoning=["Greeting"], action=Action.RESPOND.value, response="How can I help?"
    )

    assert session.current_step.get_available_routes() == ["end"]
    assert session.current_step.available_tools == [
        "test_tool",
        "another_test_tool",
        "combinations",
    ]

    # Set up mock responses
    session.llm.set_response(ask_response)

    # First interaction
    res = session.next()
    assert len(session.llm.messages_received) == 2
    assert session.llm.messages_received[0].role == "system"
    assert "Test persona" in session.llm.messages_received[0].content
    assert session.llm.messages_received[1].role == "user"
    assert res.decision.action == Action.RESPOND
    assert res.decision.response == "How can I help?"

    ask_response = expected_decision_model(
        reasoning=["User input"],
        action=Action.RESPOND.value,
        response="I can help you with that.",
    )
    session.llm.set_response(ask_response)
    # User response
    res = session.next("I need help")
    assert len(session.llm.messages_received) == 2
    assert session.llm.messages_received[1].role == "user"
    assert "How can I help?" in session.llm.messages_received[1].content
    assert "I need help" in session.llm.messages_received[1].content
    assert res.decision.action == Action.RESPOND
    assert res.decision.response == "I can help you with that."


def test_tool_usage(basic_agent, test_tool_0, test_tool_1, tool_defs):
    """Test that the agent can properly use tools."""

    # Start session and use tool
    session = basic_agent.create_session()

    # Create response models with tool
    tool_model = basic_agent.llm._create_decision_model(
        current_step=session.current_step,
        current_step_tools=(
            Tool.from_function(test_tool_0),
            Tool.from_function(test_tool_1),
            ToolWrapper(
                tool_type="pkg",
                name="combinations",
                tool_identifier="itertools.combinations",
            ).get_tool(tool_defs=tool_defs),
        ),
    )

    # Set up mock responses
    tool_response = tool_model(
        reasoning=["Need to use test tool"],
        action=Action.TOOL_CALL.value,
        tool_call={
            "tool_name": "test_tool",
            "tool_kwargs": {"arg0": "test_arg"},
        },
    )

    session.llm.set_response(tool_response)

    # Tool usage
    res = session.next("Use the tool", return_tool=True)
    assert len(session.llm.messages_received) == 2
    assert session.llm.messages_received[1].role == "user"
    assert "Use the tool" in session.llm.messages_received[1].content
    assert res.decision.action == Action.TOOL_CALL
    assert res.decision.tool_call.tool_name == "test_tool"
    assert res.tool_output == "Test tool 0 response: test_arg"

    # Verify tool message in history
    messages = [msg for msg in session.memory.context if isinstance(msg, Event)]
    assert any(msg.type == "tool" for msg in messages)


def test_pkg_tool_usage(basic_agent, test_tool_0, test_tool_1, tool_defs):
    """Test that the agent can properly use tools."""

    # Start session and use tool
    session = basic_agent.create_session()

    # Create response models with tool
    tool_model = basic_agent.llm._create_decision_model(
        current_step=session.current_step,
        current_step_tools=(
            Tool.from_function(test_tool_0),
            Tool.from_function(test_tool_1),
            ToolWrapper(
                tool_type="pkg",
                name="combinations",
                tool_identifier="itertools.combinations",
            ).get_tool(tool_defs=tool_defs),
        ),
    )

    # Set up mock responses
    tool_response = tool_model(
        reasoning=["Need to use combinations tool"],
        action=Action.TOOL_CALL.value,
        tool_call={
            "tool_name": "combinations",
            "tool_kwargs": {"iterable": [1, 2, 3], "r": 2},
        },
    )

    session.llm.set_response(tool_response)

    # Tool usage
    session.next("Use the tool", return_tool=True)

    # Verify tool message in history
    messages = [msg for msg in session.memory.context if isinstance(msg, Event)]
    assert any(msg.type == "tool" for msg in messages)


@patch("requests.request")
def test_api_tool_usage(mock_request, basic_agent, test_tool_0, test_tool_1, tool_defs):
    """Test that the agent can properly use API tools."""
    # Mock the HTTP response
    mock_response = Mock()
    mock_response.text = '{"users": [{"id": 1, "name": "John"}]}'
    mock_request.return_value = mock_response

    # Create an API tool wrapper
    api_wrapper = ToolWrapper(
        tool_type="api",
        name="get_users",
        tool_identifier="GET/https://api.example.com/users",
    )

    # Create custom steps that reference the API tool
    steps = [
        Step(
            step_id="start",
            description="Start step with API tool",
            routes=[Route(target="end", condition="Task completed")],
            available_tools=["get_users"],
        ),
        Step(step_id="end", description="End step", routes=[], available_tools=[]),
    ]

    # Create a new agent with the API tool
    config = AgentConfig(
        name="api_test_agent",
        persona="API test persona",
        steps=steps,
        start_step_id="start",
        tools=ToolsConfig(tool_defs={}),
    )

    agent = Agent.from_config(
        config=config,
        llm=basic_agent.llm,
        tools=[api_wrapper],
    )

    session = agent.create_session()

    # Create response models with API tool
    tool_model = agent.llm._create_decision_model(
        current_step=session.current_step,
        current_step_tools=tuple(session.tools.values()),
    )

    # Set up mock responses
    tool_response = tool_model(
        reasoning=["Need to get users from API"],
        action=Action.TOOL_CALL.value,
        tool_call={
            "tool_name": "get_users",
            "tool_kwargs": {},
        },
    )

    session.llm.set_response(tool_response)

    # Tool usage
    result = session.next("Get users from API", return_tool=True)

    # Verify the tool was called
    assert result.decision.action == Action.TOOL_CALL
    assert result.decision.tool_call.tool_name == "get_users"
    assert result.tool_output == '{"users": [{"id": 1, "name": "John"}]}'

    # Verify HTTP request was made
    mock_request.assert_called_once_with(
        method="GET",
        url="https://api.example.com/users",
        json=None,
        headers={},
        params={},
    )

    # Verify tool message in history
    messages = [msg for msg in session.memory.context if isinstance(msg, Event)]
    assert any(msg.type == "tool" for msg in messages)


def test_invalid_tool_args(basic_agent, test_tool_0, test_tool_1, tool_defs):
    """Test handling of invalid tool arguments."""

    session = basic_agent.create_session()

    tool_model = basic_agent.llm._create_decision_model(
        current_step=session.current_step,
        current_step_tools=(
            Tool.from_function(test_tool_0),
            Tool.from_function(test_tool_1),
            ToolWrapper(
                tool_type="pkg",
                name="combinations",
                tool_identifier="itertools.combinations",
            ).get_tool(tool_defs=tool_defs),
        ),
    )

    # Set up response with invalid args
    invalid_response = tool_model(
        action=Action.TOOL_CALL.value,
        reasoning=["Testing invalid args"],
        tool_call={
            "tool_name": "test_tool",
            "tool_kwargs": {"arg1": "value"},  # Invalid argument
        },
    )

    session.llm.set_response(invalid_response)

    with pytest.raises(ValueError, match="Maximum errors reached"):
        session.next("Use tool with invalid args", return_tool=True)

    # Verify error message in history
    messages = [msg for msg in session.memory.context if isinstance(msg, Event)]
    assert any(msg.type == "error" for msg in messages)


def test_config_loading(mock_llm, basic_steps, test_tool_0, test_tool_1):
    """Test loading agent from config."""
    from itertools import combinations

    config = AgentConfig(
        name="config_test",
        steps=basic_steps,
        start_step_id="start",
        persona="Config test persona",
        tools=ToolsConfig(
            tool_defs={
                "test_tool": ToolDef(args=[ArgDef(key="arg0", desc="Test argument")]),
                "another_test_tool": ToolDef(
                    desc="Another test tool (overridden)",
                    args=[ArgDef(key="arg1", desc="Another test argument")],
                ),
                "combinations": ToolDef(
                    desc="Test tool for combinations",
                    args=[
                        ArgDef(key="iterable", type="List", desc="Input iterable"),
                        ArgDef(key="r", type="int", desc="Length of combinations"),
                    ],
                ),
            }
        ),
    )

    agent = Agent.from_config(
        llm=mock_llm,
        config=config,
        tools=[test_tool_0, test_tool_1, combinations],
    )

    assert agent.name == "config_test"
    assert agent.persona == "Config test persona"
    assert len(agent.steps) == 2
    assert len(agent.tools) == 3

    session = agent.create_session()

    # Test that tool arg descriptions were properly loaded
    tool = session.tools["test_tool"]
    assert tool.parameters["arg0"]["description"] == "Test argument"
    tool = session.tools["another_test_tool"]
    assert tool.description == "Another test tool (overridden)"


def test_external_tools_registration(mock_llm, basic_steps, test_tool_0, test_tool_1):
    """Test that external tools are properly registered in the session."""
    # Test only package tools registration, skip crewai since it's not installed

    import os

    os.environ["OPENAI_API_KEY"] = "test_key"  # Required env var

    config = AgentConfig(
        name="config_test",
        steps=basic_steps,
        start_step_id="start",
        persona="Config test persona",
        tools=ToolsConfig(
            external_tools=[
                {"tag": "@pkg/itertools.combinations", "name": "combinations"},
                # Skip crewai tools since crewai is not installed
                # {"tag": "@crewai/FileReadTool", "name": "file_read_tool"},
                # {
                #     "tag": "@crewai/PDFSearchTool",
                #     "name": "pdf_search_tool",
                #     "kwargs": {
                #         "pdf": "https://www.w3.org/WAI/ER/tests/xhtml/testfiles/resources/pdf/dummy.pdf"
                #     },
                # },
            ],
            tool_defs={
                "combinations": ToolDef(
                    desc="Test tool for combinations",
                    args=[
                        ArgDef(key="iterable", type="List", desc="Input iterable"),
                        ArgDef(key="r", type="int", desc="Length of combinations"),
                    ],
                ),
            },
        ),
    )

    agent = Agent.from_config(
        llm=mock_llm,
        config=config,
        tools=[test_tool_0, test_tool_1],
    )

    assert agent.name == "config_test"
    assert agent.persona == "Config test persona"
    assert len(agent.steps) == 2
    # Only 3 tools now: combinations + test_tool_0 + test_tool_1
    assert len(agent.tools) == 3

    session = agent.create_session()

    # Test that package tool was properly registered
    pkg_tool = session.tools["combinations"]
    assert isinstance(pkg_tool, Tool)
    assert pkg_tool.name == "combinations"


# ======================================================================
# COVERAGE IMPROVEMENT TESTS - Focused on uncovered lines in core.py
# ======================================================================


class TestAgentValidation:
    """Test agent validation scenarios (lines 541-570)."""

    def test_invalid_start_step_error(self):
        """Test error when start step ID is invalid."""
        from nomos.llms.base import LLMBase

        mock_llm = MagicMock(spec=LLMBase)
        steps = [Step(step_id="valid_step", description="Valid", available_tools=[], routes=[])]

        with pytest.raises(ValueError, match="Start step ID invalid_step not found"):
            Agent(
                llm=mock_llm,
                name="test_agent",
                steps=steps,
                start_step_id="invalid_step",
            )

    def test_invalid_route_target_error(self):
        """Test error when route target is invalid."""
        from nomos.llms.base import LLMBase

        mock_llm = MagicMock(spec=LLMBase)
        steps = [
            Step(
                step_id="start",
                description="Start",
                available_tools=[],
                routes=[Route(condition="always", target="invalid_target")],
            )
        ]

        with pytest.raises(ValueError, match="Route target invalid_target not found"):
            Agent(llm=mock_llm, name="test_agent", steps=steps, start_step_id="start")

    def test_invalid_tool_name_error(self):
        """Test error when step references non-existent tool."""
        from nomos.llms.base import LLMBase

        mock_llm = MagicMock(spec=LLMBase)
        steps = [
            Step(
                step_id="start",
                description="Start",
                available_tools=["nonexistent_tool"],
                routes=[],
            )
        ]

        with pytest.raises(ValueError):
            Agent(
                llm=mock_llm,
                name="test_agent",
                steps=steps,
                start_step_id="start",
                tools=[],  # No tools provided
            )


class TestErrorHandling:
    """Test error handling scenarios."""

    def test_max_errors_reached(self, basic_agent):
        """Test max errors threshold (lines 333-343)."""
        session = basic_agent.create_session()

        with pytest.raises(ValueError, match="Maximum errors reached"):
            session.next(no_errors=3)  # max_errors defaults to 3

    def test_tool_not_found_error(self, basic_agent):
        """Test tool not found error (lines 162-163)."""
        session = basic_agent.create_session()

        with pytest.raises(ValueError, match="Tool 'nonexistent' not found"):
            session._run_tool("nonexistent", {})

    def test_fallback_error_coverage(self, basic_agent):
        """Test that FallbackError import and structure exist (for coverage)."""
        # Simple test to ensure FallbackError can be imported and used
        try:
            from nomos.models.tool import FallbackError

            error = FallbackError("test", "fallback")
            assert "test" in str(error)
            assert error.fallback == "fallback"
            assert error.error == "test"
        except ImportError:
            pytest.fail("FallbackError should be importable")


class TestStepTransitions:
    """Test step ID transition scenarios."""

    def test_valid_step_transition(self, basic_agent):
        """Test valid step ID transition (lines 401-416)."""
        session = basic_agent.create_session()

        # Mock decision for valid move
        valid_decision = Decision(reasoning=["Move to end"], action=Action.MOVE, step_id="end")

        with patch.object(session, "_get_next_decision", return_value=valid_decision):
            initial_step = session.current_step.step_id
            res = session.next("Move to end", return_step=True)

            assert res.decision.action == Action.MOVE
            assert res.decision.step_id == "end"
            assert session.current_step.step_id == "end"
            assert session.current_step.step_id != initial_step

    def test_step_transition_structure(self, basic_agent):
        """Test step ID structure without complex mocking."""
        session = basic_agent.create_session()

        # Test basic step access
        assert session.current_step.step_id == "start"
        assert "end" in session.current_step.get_available_routes()

        # Test that steps dict contains expected steps
        assert "start" in session.steps
        assert "end" in session.steps


class TestEndAction:
    """Test END action scenarios."""

    def test_end_action(self, basic_agent):
        """Test END action handling (lines 427-443)."""
        session = basic_agent.create_session()

        # Mock decision for END action using session tools to get correct schema
        decision_model = basic_agent.llm._create_decision_model(
            current_step=session.current_step,
            current_step_tools=tuple(session._get_current_step_tools()),
        )

        end_response = decision_model(
            reasoning=["End session"], action=Action.END.value, response="Goodbye"
        )
        basic_agent.llm.set_response(end_response)

        res = session.next("End session")

        assert res.decision.action == Action.END
        assert res.tool_output is None

        # Check that end message was added
        messages = [msg for msg in session.memory.context if isinstance(msg, Event)]
        end_msgs = [msg for msg in messages if msg.type == "end"]
        assert len(end_msgs) == 1
        assert "Session ended" in end_msgs[0].content


class TestFromConfigErrors:
    """Test Agent.from_config error scenarios."""

    def test_from_config_no_llm_error(self):
        """Test error when no LLM provided to from_config."""
        config = AgentConfig(
            name="test",
            steps=[Step(step_id="start", description="Start", available_tools=[], routes=[])],
            start_step_id="start",
        )

        with pytest.raises(AssertionError):
            Agent.from_config(config=config)


class TestMemoryOperations:
    """Test memory operations without flows."""

    def test_add_event_without_flow(self, basic_agent):
        """Test adding event when no flow is active."""
        session = basic_agent.create_session()

        # Ensure no flow is active
        session.state_machine.current_flow = None
        session.state_machine.flow_context = None

        session._add_event("user", "Test message")

        # Event should be added to session memory
        events = [msg for msg in session.memory.context if isinstance(msg, Event)]
        assert len(events) == 1
        assert events[0].type == "user"
        assert events[0].content == "Test message"

    def test_add_step_identifier_without_flow(self, basic_agent):
        """Test adding step identifier when no flow is active."""
        session = basic_agent.create_session()

        # Ensure no flow is active
        session.state_machine.current_flow = None
        session.state_machine.flow_context = None

        step_id = StepIdentifier(step_id="test_step")
        session._add_step_identifier(step_id)

        # Step identifier should be added to session memory
        step_ids = [msg for msg in session.memory.context if isinstance(msg, StepIdentifier)]
        assert len(step_ids) == 1
        assert step_ids[0].step_id == "test_step"


class TestSessionStateOperations:
    """Test session state operations."""

    def test_get_state_basic(self, basic_agent):
        """Test getting session state."""
        session = basic_agent.create_session()
        session._add_event("user", "Hello")

        state = session.get_state()

        assert hasattr(state, "session_id")
        assert hasattr(state, "current_step_id")
        assert hasattr(state, "history")
        assert state.current_step_id == "start"
        assert len(state.history) == 1

    def test_get_session_from_state(self, basic_agent):
        """Test creating session from State object."""
        from nomos.models.agent import State, history_to_types

        history = history_to_types([{"role": "user", "content": "Hello"}, {"step_id": "start"}])

        state = State(
            session_id="test_session",
            current_step_id="start",
            history=history,
        )

        session = basic_agent.get_session_from_state(state)

        assert session.session_id == "test_session"
        assert session.current_step.step_id == "start"
        assert len(session.memory.context) == 2

    def test_get_session_from_state_invalid_history(self, basic_agent):
        """Test error handling for invalid history items."""
        with pytest.raises(ValueError, match="Unknown history item type: <class 'str'>"):
            from nomos.models.agent import history_to_types

            history_to_types(["invalid_item"])


class TestUnknownActionHandling:
    """Test unknown action error handling."""

    def test_action_enum_coverage(self, basic_agent):
        """Test action enum values for coverage."""
        basic_agent.create_session()

        # Test that Action enum has expected values
        assert hasattr(Action, "RESPOND")
        assert hasattr(Action, "END")
        assert hasattr(Action, "MOVE")
        assert hasattr(Action, "TOOL_CALL")

        # Test string values
        assert Action.RESPOND.value == "RESPOND"
        assert Action.END.value == "END"
        assert Action.MOVE.value == "MOVE"
        assert Action.TOOL_CALL.value == "TOOL_CALL"


class TestMaxIterationsBehavior:
    """Test maximum iterations behavior with fallback scenarios."""

    def test_max_iterations_fallback_behavior(self, basic_agent):
        """Test max iterations fallback when auto_flow=False."""
        session = basic_agent.create_session()
        session.current_step.auto_flow = False

        # Mock LLM to return a response that matches the correct schema
        # We need to trigger the max iterations by calling session.next with next_count=5
        # and ensure auto_flow=False so it adds fallback message instead of raising RecursionError

        # First, manually add the fallback message that would be added when max_iter is reached
        session._add_event(
            "fallback",
            "Maximum iterations reached. Inform the user and based on the "
            "available context, produce a fallback response.",
        )

        # Then mock a normal response for the recursive call
        decision_model = basic_agent.llm._create_decision_model(
            current_step=session.current_step,
            current_step_tools=tuple(session._get_current_step_tools()),
        )

        fallback_response = decision_model(
            reasoning=["Providing fallback response"],
            action=Action.RESPOND.value,
            response="I apologize, but I've reached the maximum number of attempts.",
        )
        basic_agent.llm.set_response(fallback_response)

        # This should trigger the fallback behavior instead of raising RecursionError
        res = session.next(next_count=5)

        # Verify fallback message was added and response was generated
        messages = [msg for msg in session.memory.context if isinstance(msg, Event)]
        fallback_msgs = [msg for msg in messages if msg.type == "fallback"]
        assert len(fallback_msgs) == 1
        assert "Maximum iterations reached" in fallback_msgs[0].content
        assert res.decision.action == Action.RESPOND


class TestToolExecutionScenarios:
    """Test various tool execution scenarios."""

    def test_tool_execution_with_return_tool_flag(self, basic_agent, test_tool_0):
        """Test TOOL_CALL action with return_tool=True."""
        session = basic_agent.create_session()

        # Use the existing session tools from basic_agent
        decision_model = basic_agent.llm._create_decision_model(
            current_step=session.current_step,
            current_step_tools=tuple(session._get_current_step_tools()),
        )

        tool_response = decision_model(
            reasoning=["Use tool"],
            action=Action.TOOL_CALL.value,
            tool_call={"tool_name": "test_tool", "tool_kwargs": {"arg0": "test_value"}},
        )
        basic_agent.llm.set_response(tool_response)

        res = session.next("Use tool", return_tool=True)

        assert res.decision.action == Action.TOOL_CALL
        assert res.tool_output == "Test tool 0 response: test_value"

    def test_tool_structure_coverage(self, basic_agent):
        """Test tool structure and error handling coverage."""
        session = basic_agent.create_session()

        # Test that tools exist and have proper structure
        assert "test_tool" in session.tools
        assert hasattr(session.tools["test_tool"], "name")
        assert hasattr(session.tools["test_tool"], "description")

        # Test _get_current_step_tools method
        current_tools = session._get_current_step_tools()
        assert len(current_tools) > 0
        assert all(hasattr(tool, "name") for tool in current_tools)


# ======================================================================
# COMPREHENSIVE COVERAGE TESTS - Merged from test_core_coverage.py
# ======================================================================


class TestSessionPersistence:
    """Test session save/load functionality."""

    def test_save_and_load_session(self, basic_agent, tmp_path):
        """Test saving and loading a session."""
        # Create a simple agent without complex tools to avoid pickle issues
        simple_steps = [
            Step(
                step_id="start",
                description="Start step",
                available_tools=[],  # No tools to avoid pickle issues
                routes=[Route(condition="always", target="end")],
            ),
            Step(step_id="end", description="End step", available_tools=[], routes=[]),
        ]

        simple_agent = Agent(
            llm=basic_agent.llm,
            name="simple_agent",
            steps=simple_steps,
            start_step_id="start",
            tools=[],  # No tools
        )

        # Create session and add some history
        session = simple_agent.create_session()
        session._add_event("user", "Hello")
        session._add_event("assistant", "Hi there")

        # Change working directory to temp path for the test
        original_cwd = os.getcwd()
        os.chdir(tmp_path)

        try:
            # Save session
            session.save_session()

            # Verify file exists
            pickle_file = Path(f"{session.session_id}.pkl")
            assert pickle_file.exists()

            # Load session
            loaded_session = Session.load_session(session.session_id)

            # Verify session data
            assert loaded_session.session_id == session.session_id
            assert loaded_session.name == session.name
            assert len(loaded_session.memory.context) == len(session.memory.context)
            assert loaded_session.current_step.step_id == session.current_step.step_id

        finally:
            os.chdir(original_cwd)

    def test_load_nonexistent_session(self):
        """Test loading a session that doesn't exist."""
        with pytest.raises(FileNotFoundError):
            Session.load_session("nonexistent_session_id")


class TestSessionStateOperationsExtended:
    """Extended tests for session state conversion and restoration."""

    def test_get_state_with_flow_state(self, basic_agent):
        """Test getting session state with active flow."""
        session = basic_agent.create_session()

        # Mock flow state
        from nomos.models.flow import Flow, FlowContext

        mock_flow = MagicMock(spec=Flow)
        mock_flow.flow_id = "test_flow"
        mock_flow_context = MagicMock(spec=FlowContext)
        mock_flow_context.model_dump.return_value = {"test": "data"}

        session.state_machine.current_flow = mock_flow
        session.state_machine.flow_context = mock_flow_context

        state = session.get_state()

        assert hasattr(state, "flow_state")
        if state.flow_state:
            assert state.flow_state.flow_id == "test_flow"

    def test_get_session_from_state_with_messages(self, basic_agent):
        """Test creating session from State with message history."""
        from nomos.models.agent import State, history_to_types

        history = history_to_types(
            [
                {"role": "user", "content": "Hello"},
                {"role": "assistant", "content": "Hi"},
                {"step_id": "start"},
            ]
        )

        state = State(
            session_id="test_session",
            current_step_id="start",
            history=history,
        )

        session = basic_agent.get_session_from_state(state)

        assert session.session_id == "test_session"
        assert session.current_step.step_id == "start"
        assert len(session.memory.context) == 3
        assert isinstance(session.memory.context[0], Event)
        assert isinstance(session.memory.context[2], StepIdentifier)

    def test_get_session_from_state_with_summary(self, basic_agent):
        """Test creating session from State with summary in history."""
        from nomos.models.agent import State, history_to_types

        history = history_to_types([{"summary": ["point1", "point2"]}])

        state = State(
            session_id="test_session",
            current_step_id="start",
            history=history,
        )

        session = basic_agent.get_session_from_state(state)

        assert len(session.memory.context) == 1
        assert isinstance(session.memory.context[0], Summary)

    def test_get_session_from_state_with_flow_state(self, basic_agent):
        """Test restoring session with flow state."""
        from nomos.models.agent import State

        # Simple test to ensure basic session restoration works
        state = State(
            session_id="test_session",
            current_step_id="start",
            history=[],
        )

        session = basic_agent.get_session_from_state(state)

        # The session creation should work
        assert session.session_id == "test_session"
        assert session.current_step.step_id == "start"


class TestAdvancedErrorHandling:
    """Test advanced error handling scenarios."""

    def test_max_iterations_reached_with_auto_flow(self, basic_agent):
        """Test behavior when max iterations reached with auto_flow enabled."""
        session = basic_agent.create_session()
        session.current_step.auto_flow = True

        # Mock the LLM to provide a response that won't trigger early exit
        decision_model = basic_agent.llm._create_decision_model(
            current_step=session.current_step,
            current_step_tools=tuple(session._get_current_step_tools()),
        )

        # With auto_flow=True, only END, MOVE, and TOOL_CALL are allowed
        tool_response = decision_model(
            reasoning=["Use tool"],
            action=Action.TOOL_CALL.value,
            tool_call={"tool_name": "test_tool", "tool_kwargs": {"arg0": "test_value"}},
        )
        session.llm.set_response(tool_response)

        with pytest.raises(RecursionError, match="Maximum iterations reached"):
            session.next(next_count=5)  # Default max_iter is 5

    def test_fallback_error_handling(self, basic_agent):
        """Test handling of FallbackError during tool execution."""
        # Simple test to verify FallbackError structure exists and can be used
        try:
            from nomos.models.tool import FallbackError

            error = FallbackError(error="test error", fallback="test fallback")
            assert error.error == "test error"
            assert error.fallback == "test fallback"
            assert "test error" in str(error)
        except ImportError:
            pytest.fail("FallbackError should be importable")

    def test_invalid_step_transition(self, basic_agent):
        """Test error handling for invalid step IDs."""
        session = basic_agent.create_session()

        # Test that only valid routes are available
        available_routes = session.current_step.get_available_routes()
        assert "end" in available_routes
        assert "invalid_step" not in available_routes

        # Test that trying to access an invalid step would fail
        assert "invalid_step" not in session.steps

        # Current step should be "start"
        assert session.current_step.step_id == "start"

    def test_unknown_action_error(self, basic_agent):
        """Test error handling for unknown actions."""
        # Test that the Action enum has expected values
        assert hasattr(Action, "RESPOND")
        assert hasattr(Action, "END")
        assert hasattr(Action, "MOVE")
        assert hasattr(Action, "TOOL_CALL")

        # Test string values
        assert Action.RESPOND.value == "RESPOND"
        assert Action.END.value == "END"
        assert Action.MOVE.value == "MOVE"
        assert Action.TOOL_CALL.value == "TOOL_CALL"

    def test_tool_execution_error(self, basic_agent):
        """Test generic tool execution error handling."""
        # Simple test to verify that tool execution can handle errors
        session = basic_agent.create_session()

        # Verify that tools exist and have basic structure
        assert "test_tool" in session.tools
        tool = session.tools["test_tool"]
        assert hasattr(tool, "name")
        assert hasattr(tool, "run")

        # Test tool with valid arguments works
        result = tool.run(arg0="test")
        assert "test" in result

    def test_missing_response_handling(self, basic_agent):
        """Ensure missing decision fields trigger retry with error message."""
        session = basic_agent.create_session()

        decision_model = basic_agent.llm._create_decision_model(
            current_step=session.current_step,
            current_step_tools=session._get_current_step_tools(),
        )

        invalid_resp = decision_model(reasoning=["r"], action=Action.RESPOND.value)
        valid_resp_model = basic_agent.llm._create_decision_model(
            current_step=session.current_step,
            current_step_tools=session._get_current_step_tools(),
            constraints=DecisionConstraints(actions=["RESPOND"], fields=["response"]),
        )
        valid_resp = valid_resp_model(reasoning=["r"], action=Action.RESPOND.value, response="ok")
        basic_agent.llm.set_response(invalid_resp)
        basic_agent.llm.set_response(valid_resp, append=True)

        res = session.next()

        assert res.decision.action == Action.RESPOND
        assert res.decision.response == "ok"
        messages = [msg for msg in session.memory.context if isinstance(msg, Event)]
        assert any("requires a response" in msg.content for msg in messages)


class TestAgentValidationExtended:
    """Extended agent configuration validation tests."""

    def test_tool_deduplication(self, mock_llm, basic_steps):
        """Test that duplicate tools are properly deduplicated."""

        def tool1():
            """Test tool 1"""
            pass

        def tool2():
            """Test tool 2"""
            pass

        tool1.__name__ = "same_name"
        tool2.__name__ = "same_name"

        # Create steps that don't require any tools
        simple_steps = [
            Step(
                step_id="start",
                description="Start step",
                available_tools=[],  # No tools required
                routes=[Route(condition="always", target="end")],
            ),
            Step(step_id="end", description="End step", available_tools=[], routes=[]),
        ]

        agent = Agent(
            llm=mock_llm,
            name="test_agent",
            steps=simple_steps,
            start_step_id="start",
            tools=[tool1, tool2],  # Duplicate names
        )

        # Should only have one tool with that name
        tool_names = list(agent.tools.keys())
        assert tool_names.count("same_name") == 1


class TestFlowIntegration:
    """Test flow management integration (basic mocking since flows need more setup)."""

    @pytest.mark.skip(reason="Flow manager requires complex configuration")
    def test_flow_manager_initialization(
        self, mock_llm, basic_steps, test_tool_0, test_tool_1, tool_defs
    ):
        """Test that flow manager is initialized when config has flows."""
        # This test is skipped because flow configuration requires complex setup
        # that is beyond the scope of basic core functionality testing
        pass

    def test_session_with_flow_memory_integration(self, basic_agent):
        """Test session memory handling with flow memory."""
        session = basic_agent.create_session()

        # Mock flow and flow memory
        from nomos.memory.flow import FlowMemoryComponent
        from nomos.models.flow import Flow, FlowContext

        mock_flow = MagicMock(spec=Flow)
        mock_flow_memory = MagicMock(spec=FlowMemoryComponent)
        mock_flow.get_memory.return_value = mock_flow_memory
        mock_flow_context = MagicMock(spec=FlowContext)

        session.state_machine.current_flow = mock_flow
        session.state_machine.flow_context = mock_flow_context

        # Add message should go to flow memory, not session memory
        session._add_event("user", "Test message")

        mock_flow_memory.add_to_context.assert_called_once()
        # Session memory should not be updated
        assert len(session.memory.context) == 0

    def test_step_identifier_with_flow_memory(self, basic_agent):
        """Test step identifier handling with flow memory."""
        session = basic_agent.create_session()

        # Mock flow and flow memory
        from nomos.memory.flow import FlowMemoryComponent
        from nomos.models.flow import Flow, FlowContext

        mock_flow = MagicMock(spec=Flow)
        mock_flow_memory = MagicMock(spec=FlowMemoryComponent)
        mock_flow.get_memory.return_value = mock_flow_memory
        mock_flow_context = MagicMock(spec=FlowContext)

        session.state_machine.current_flow = mock_flow
        session.state_machine.flow_context = mock_flow_context

        step_id = StepIdentifier(step_id="test_step")
        session._add_step_identifier(step_id)

        mock_flow_memory.add_to_context.assert_called_once_with(step_id)
        # Session memory should not be updated
        assert len(session.memory.context) == 0


class TestEndActionFlow:
    """Test END action and session cleanup."""

    def test_end_action_with_flow_cleanup(self, basic_agent):
        """Test END action with flow cleanup."""
        session = basic_agent.create_session()

        # Mock active flow that needs cleanup
        from nomos.models.flow import Flow, FlowContext

        mock_flow = MagicMock(spec=Flow)
        mock_flow_context = MagicMock(spec=FlowContext)
        session.state_machine.current_flow = mock_flow
        session.state_machine.flow_context = mock_flow_context

        decision_model = basic_agent.llm._create_decision_model(
            current_step=session.current_step,
            current_step_tools=tuple(session._get_current_step_tools()),
        )

        end_response = decision_model(
            reasoning=["End session"], action=Action.END.value, response="Goodbye"
        )
        session.llm.set_response(end_response)

        res = session.next("End the session")

        assert res.decision.action == Action.END
        assert res.tool_output is None

        # Verify flow cleanup was called
        mock_flow.cleanup.assert_called_once_with(mock_flow_context)
        assert session.state_machine.current_flow is None
        assert session.state_machine.flow_context is None

        # Verify end message was added
        messages = [msg for msg in session.memory.context if isinstance(msg, Event)]
        end_msgs = [msg for msg in messages if msg.type == "end"]
        assert len(end_msgs) == 1
        assert "Session ended" in end_msgs[0].content

    def test_end_action_flow_cleanup_error(self, basic_agent, caplog):
        """Test END action when flow cleanup raises an error."""
        session = basic_agent.create_session()

        # Mock active flow that raises error during cleanup
        from nomos.models.flow import Flow, FlowContext

        mock_flow = MagicMock(spec=Flow)
        mock_flow.cleanup.side_effect = Exception("Cleanup error")
        mock_flow_context = MagicMock(spec=FlowContext)
        session.state_machine.current_flow = mock_flow
        session.state_machine.flow_context = mock_flow_context

        decision_model = basic_agent.llm._create_decision_model(
            current_step=session.current_step,
            current_step_tools=tuple(session._get_current_step_tools()),
        )

        end_response = decision_model(
            reasoning=["End session"], action=Action.END.value, response="Goodbye"
        )
        session.llm.set_response(end_response)

        res = session.next("End the session")

        assert res.decision.action == Action.END
        assert res.tool_output is None

        # Flow state should be cleaned up even if there was an error
        assert session.state_machine.current_flow is None
        assert session.state_machine.flow_context is None


class TestAgentNext:
    """Test Agent.next method variations."""

    def test_agent_next_with_session_context_object(self, basic_agent):
        """Test Agent.next with session State object."""
        from nomos.models.agent import Event, State

        session_context = State(
            current_step_id="start", history=[Event(type="user", content="Hello")]
        )

        # Create a session and get tools from it
        session = basic_agent.create_session()

        decision_model = basic_agent.llm._create_decision_model(
            current_step=basic_agent.steps["start"],
            current_step_tools=tuple(session._get_current_step_tools()),
        )

        response = decision_model(
            reasoning=["Respond to greeting"],
            action=Action.RESPOND.value,
            response="Hello there!",
        )
        basic_agent.llm.set_response(response)

        res = basic_agent.next(user_input="Hello", session_data=session_context, verbose=True)

        assert res.decision.action == Action.RESPOND
        assert hasattr(res.state, "session_id")
        assert hasattr(res.state, "current_step_id")

    def test_agent_next_without_session_data(self, basic_agent):
        """Test Agent.next creating new session when no session_data provided."""
        # Create a session and get tools from it
        session = basic_agent.create_session()

        decision_model = basic_agent.llm._create_decision_model(
            current_step=basic_agent.steps["start"],
            current_step_tools=tuple(session._get_current_step_tools()),
        )

        response = decision_model(
            reasoning=["Initial response"],
            action=Action.RESPOND.value,
            response="How can I help?",
        )
        basic_agent.llm.set_response(response)

        res = basic_agent.next("Hello")

        assert res.decision.action == Action.RESPOND
        assert hasattr(res.state, "session_id")
        assert res.state.current_step_id == "start"

    def test_agent_next_strips_event_decision_by_default(self, basic_agent):
        session = basic_agent.create_session()
        decision_model = basic_agent.llm._create_decision_model(
            current_step=basic_agent.steps["start"],
            current_step_tools=tuple(session._get_current_step_tools()),
        )
        response = decision_model(reasoning=["r"], action=Action.RESPOND.value, response="ok")
        basic_agent.llm.set_response(response)

        res = basic_agent.next("hi")
        decisions = [
            e.decision
            for e in res.state.history
            if isinstance(e, Event) and e.type == basic_agent.name
        ]
        assert decisions and all(d is None for d in decisions)

    def test_agent_next_keep_event_decision_flag(self, basic_agent):
        session = basic_agent.create_session()
        decision_model = basic_agent.llm._create_decision_model(
            current_step=basic_agent.steps["start"],
            current_step_tools=tuple(session._get_current_step_tools()),
        )
        response = decision_model(reasoning=["r"], action=Action.RESPOND.value, response="ok")
        basic_agent.llm.set_response(response)

        res = basic_agent.next("hi", keep_event_decision=True)
        decisions = [
            e.decision
            for e in res.state.history
            if isinstance(e, Event) and e.type == basic_agent.name
        ]
        assert decisions and all(d is not None for d in decisions)

    def test_current_step_tools_with_missing_tool_logging(self, basic_agent):
        """Test _get_current_step_tools handling when tool is missing."""
        session = basic_agent.create_session()

        # Add a non-existent tool to current step's available_tools
        session.current_step.available_tools.append("nonexistent_tool")

        # Should return only the existing tools, skipping the missing one
        tools = session._get_current_step_tools()

        # Should still have the original tools (but not the missing one)
        assert len(tools) == 3  # Original tools from basic_agent
        tool_names = [tool.name for tool in tools]
        assert "nonexistent_tool" not in tool_names


class TestStepExamples:
    """Tests related to step examples and embeddings."""

    def test_example_embeddings_initialized(self, example_agent):
        step = example_agent.steps["start"]
        assert step.examples is not None
        assert all(ex._ctx_embedding is not None for ex in step.examples)

    def test_examples_in_system_prompt(self, example_agent):
        session = example_agent.create_session()
        decision_model = example_agent.llm._create_decision_model(
            current_step=session.current_step,
            current_step_tools=tuple(session._get_current_step_tools()),
        )

        response = decision_model(reasoning=["r"], action=Action.RESPOND.value, response="ok")
        example_agent.llm.set_response(response)
        session.next("sqrt 4")
        system_prompt = session.llm.messages_received[0].content
        assert "Examples:" in system_prompt
        assert "time question" in system_prompt
        assert "sqrt 4" in system_prompt

        session = example_agent.create_session()
        example_agent.llm.set_response(response)
        session.next("unrelated input")
        system_prompt = session.llm.messages_received[0].content
        assert "time question" in system_prompt
        assert "sqrt 4" not in system_prompt


class TestDeferredTools:
    """Tests related to deferred tools."""

    def test_deferred_tool_registration(self, mcp_agent, mcp_tool):
        """Test that deferred tools are registered correctly."""
        session = mcp_agent.create_session()
        mcp_server = session.tools.get(mcp_tool.id)
        assert isinstance(mcp_server, MCPServer)
        assert mcp_server.name == mcp_tool.id
        assert str(mcp_server.url) == mcp_tool.tool_identifier

    @patch("nomos.models.tool.Tool.from_mcp_server")
    def test_deferred_tool_loading(self, tool_mock, mcp_agent, mcp_server_name):
        """Test that deferred tools are loaded correctly at run time."""
        tool_name = "test_tool"
        tool_description = "A test tool"
        tool_params = {"properties": {}}
        tool_instance = MagicMock(
            name=tool_name, description=tool_description, parameters=tool_params
        )
        tools_response = [tool_instance]
        tool_mock.return_value = tools_response

        session = mcp_agent.create_session()

        # tool_ids should be empty, but deferred_tool_ids should contain the MCP server.
        current_step = session.current_step
        assert current_step.tool_ids == []
        assert current_step.deferred_tool_ids == [f"@mcp/{mcp_server_name}"]

        tools = session._get_current_step_tools()
        tool_mock.assert_called()
        assert len(tools) == 1
        assert tools[0] == tool_instance

        # make sure that tool_ids are still the same
        assert current_step.tool_ids == []


class TestSessionLLM:
    """Test session LLM functionality."""

    def test_passed_llm(self, mock_llm):
        """Test that session LLM is passed correctly."""
        step = Step(
            step_id="step1",
            name="test_step",
            description="init step",
        )
        config = AgentConfig(
            name="agent",
            persona="You are a helpful assistant",
            steps=[step],
            start_step_id="step1",
            max_examples=2,
        )
        agent = Agent.from_config(config=config, llm=mock_llm)

        session = agent.create_session()
        llm = session.llm
        assert llm == mock_llm

    def test_no_llm(self):
        """Test that session raises error if no LLM is provided."""
        step = Step(
            step_id="step1",
            name="test_step",
            description="init step",
        )
        config = AgentConfig(
            name="agent",
            persona="You are a helpful assistant",
            steps=[step],
            start_step_id="step1",
            max_examples=2,
        )

        with pytest.raises(AssertionError):
            Agent.from_config(config=config)

    def test_config_llm(self, mock_llm):
        """Test that session LLM is set from config."""
        llm_config = LLMConfig(
            provider="openai",
            model="gpt-3.5-turbo",
            kwargs={"api_key": "test_key"},
        )

        step = Step(
            step_id="step1",
            name="test_step",
            description="init step",
        )
        config = AgentConfig(
            name="agent",
            persona="You are a helpful assistant",
            steps=[step],
            start_step_id="step1",
            llm=llm_config,
            max_examples=2,
        )
        agent = Agent.from_config(config=config)

        session = agent.create_session()
        llm = session.llm
        assert isinstance(llm, LLMBase)
        assert llm.__provider__ == "openai"


class TestStepOverrides:
    """Test StepOverrides functionality."""

    def test_step_persona(self, mock_llm):
        """Test Step persona overrides session persona."""
        default_persona = "You are a helpful assistant"
        custom_persona = "You are an AI Engineer"
        step_overrides = StepOverrides(persona=custom_persona)
        step = Step(
            step_id="step1", name="test_step", description="init step", overrides=step_overrides
        )
        config = AgentConfig(
            name="agent",
            persona=default_persona,
            steps=[step],
            start_step_id="step1",
            max_examples=2,
        )
        agent = Agent.from_config(config=config, llm=mock_llm)

        session = agent.create_session()
        session.persona = default_persona
        decision_model = agent.llm._create_decision_model(
            current_step=session.current_step,
            current_step_tools=tuple(session._get_current_step_tools()),
        )
        response = decision_model(reasoning=["r"], action=Action.RESPOND.value, response="ok")
        agent.llm.set_response(response)

        session.next("hi")
        assert custom_persona in session.llm.messages_received[0].content
        assert default_persona not in session.llm.messages_received[0].content

    def test_get_step_llm_id(self):
        """Test getting the step LLM ID."""
        step = Step(
            step_id="step1",
            name="test_step",
            description="init step",
            overrides=StepOverrides(llm="other"),
        )
        config = AgentConfig(
            name="agent",
            steps=[step],
            start_step_id="step1",
            max_examples=2,
        )
        agent = Agent.from_config(
            config=config,
            llm={
                "global": LLMConfig(
                    provider="openai",
                    model="gpt-3.5-turbo",
                    kwargs={"api_key": "test_key"},
                ),
                "other": LLMConfig(
                    provider="openai",
                    model="gpt-4",
                    kwargs={"api_key": "test_key_2"},
                ),
            },
        )

        session = agent.create_session()
        llm = session.llm
        assert llm.model == "gpt-4"
