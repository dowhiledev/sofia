"""Core models and logic for the Nomos package, including flow management and session handling."""

import contextlib
import pickle
import uuid
from typing import Any, Callable, Dict, List, Optional, Union

from pydantic import BaseModel

from .config import AgentConfig
from .constants import ACTION_ENUMS
from .llms import LLMBase
from .memory.base import Memory
from .memory.flow import FlowMemoryComponent
from .models.agent import (
    Message,
    Step,
    StepIdentifier,
    Summary,
    create_decision_model,
)
from .models.flow import Flow, FlowContext, FlowManager
from .models.tool import (
    FallbackError,
    MCPServer,
    RemoteTool,
    Tool,
    is_package_tool,
    is_remote_tool,
)
from .utils.flow_utils import (
    create_flows_from_config,
    should_enter_flow,
    should_exit_flow,
)
from .utils.logging import log_debug, log_error, log_info


class Session:
    """Manages a single agent session, including step transitions, tool calls, and history."""

    def __init__(
        self,
        name: str,
        llm: LLMBase,
        memory: Memory,
        steps: Dict[str, Step],
        start_step_id: str,
        system_message: Optional[str] = None,
        persona: Optional[str] = None,
        tools: Optional[List[Union[Callable, str]]] = None,
        mcp_servers: Optional[List[MCPServer]] = None,
        show_steps_desc: bool = False,
        max_errors: int = 3,
        max_iter: int = 5,
        config: Optional[AgentConfig] = None,
        history: Optional[List[Union[Message, StepIdentifier, Summary]]] = None,
        current_step_id: Optional[str] = None,
        session_id: Optional[str] = None,
        verbose: bool = False,
    ) -> None:
        """
        Initialize a Session.

        :param name: Name of the agent.
        :param llm: LLMBase instance.
        :param steps: Dictionary of step_id to Step.
        :param start_step_id: ID of the starting step.
        :param system_message: Optional system message.
        :param persona: Optional persona string.
        :param tools:  List of tool callables or package identifiers (e.g., "math:add").
        :param mcp_servers: List of MCPServer instances for tool discovery.
        :param show_steps_desc: Whether to show step descriptions.
        :param max_errors: Maximum consecutive errors before stopping or fallback. (Defaults to 3)
        :param max_iter: Maximum number of decision loops for single action. (Defaults to 5)
        :param config: Optional AgentConfig.
        :param history: List of messages and steps in the session. (Optional)
        :param current_step_id: Current step ID. (Defaults to start_step_id)
        :param session_id: Unique session ID. (Defaults to a UUID)
        """
        # Fixed
        self.session_id = session_id or f"{name}_{str(uuid.uuid4())}"
        self.name = name
        self.llm = llm
        self.steps = steps
        self.show_steps_desc = show_steps_desc
        self.system_message = system_message
        self.persona = persona
        self.max_errors = max_errors
        self.max_iter = max_iter
        self.verbose = verbose
        self.config = config

        # Flow management
        self.flow_manager: Optional[FlowManager] = None
        self.current_flow: Optional[Flow] = None
        self.flow_context: Optional[FlowContext] = None

        if config and config.flows:
            self.flow_manager = create_flows_from_config(config)
            log_debug(
                f"Flow manager initialized with {len(self.flow_manager.flows)} flows"
            )

        # MCP servers management
        self.mcp_servers = {
            mcp.name: mcp for mcp in mcp_servers or []
        }  # Ensure unique MCP servers

        tool_arg_descs = (
            self.config.tool_arg_descriptions
            if self.config and self.config.tool_arg_descriptions
            else {}
        )
        tools_list = [
            (
                Tool.from_function(tool, tool_arg_descs)
                if callable(tool)
                else Tool.from_pkg(tool, tool_arg_descs)
            )
            for tool in tools or []
        ]
        self.tools = {tool.name: tool for tool in tools_list}
        # Variable
        self.memory = memory
        self.memory.context = history or []
        self.current_step: Step = (
            steps[current_step_id] if current_step_id else steps[start_step_id]
        )
        # For OpenTelemetry tracing context
        self._otel_root_span_ctx: Any = None

    def save_session(self) -> None:
        """Save the current session to disk as a pickle file."""
        with open(f"{self.session_id}.pkl", "wb") as f:
            pickle.dump(self, f)
        log_debug(f"Session {self.session_id} saved to disk.")

    @classmethod
    def load_session(cls, session_id: str) -> "Session":
        """
        Load a Session from disk by session_id.

        :param session_id: The session ID string.
        :return: Loaded Session instance.
        """
        with open(f"{session_id}.pkl", "rb") as f:
            log_debug(f"Session {session_id} loaded from disk.")
            return pickle.load(f)

    def to_dict(self) -> dict[str, Any]:
        """
        Convert the session to a dictionary representation.

        :return: Dictionary representation of the session.
        """
        session_dict = {
            "session_id": self.session_id,
            "current_step_id": self.current_step.step_id,
            "history": [msg.model_dump(mode="json") for msg in self.memory.context],
        }

        # Include flow state if active
        if self.current_flow and self.flow_context:
            session_dict["flow_state"] = {
                "flow_id": self.current_flow.flow_id,
                "flow_context": self.flow_context.model_dump(mode="json"),
            }  # type: ignore

        return session_dict

    def _run_tool(self, tool_name: str, kwargs: Dict[str, Any]) -> Any:  # noqa: ANN401
        """
        Run a tool with the given name and arguments.

        :param tool_name: Name of the tool to run.
        :param kwargs: Arguments to pass to the tool.
        :return: Result of the tool execution.
        """
        tool = self.tools.get(tool_name)
        if not tool:
            log_error(f"Tool '{tool_name}' not found in session tools.")
            raise ValueError(
                f"Tool '{tool_name}' not found in session tools. Please check the tool name."
            )

        log_debug(f"Running tool: {tool_name} with args: {kwargs}")
        return tool.run(**kwargs)

    def _get_current_step_tools(self) -> List[Tool]:
        """
        Get the list of tools available in the current step.

        :return: List of Tool instances available in the current step.
        """
        tools = []
        for tool in self.current_step.tool_ids:
            _tool = self.tools.get(tool)
            if not _tool:
                log_error(f"Tool '{tool}' not found in session tools. Skipping.")
                continue
            tools.append(_tool)
        return tools

    def _add_message(self, role: str, message: str) -> None:
        """
        Add a message to the session history.

        :param role: Role of the message sender (e.g., 'user', 'assistant', 'tool').
        :param message: The message content.
        """
        message_obj = Message(role=role, content=message)

        # If we're in a flow, only update flow memory
        if self.current_flow and self.flow_context:
            flow_memory = self.current_flow.get_memory()
            if flow_memory and isinstance(flow_memory, FlowMemoryComponent):
                flow_memory.add_to_context(message_obj)
            # Don't update session memory while in flow
        else:
            # Only update session memory when not in a flow
            self.memory.add(message_obj)

        log_debug(f"{role.title()} added: {message}")

    def _handle_flow_transitions(self) -> None:
        """Handle flow entry and exit based on current step."""
        if not self.flow_manager:
            return

        current_step_id = self.current_step.step_id

        # Check if we should enter any flows
        entry_flows = should_enter_flow(self.flow_manager, current_step_id)
        if entry_flows and not self.current_flow:
            # Enter the first matching flow
            flow_to_enter = entry_flows[0]
            self._enter_flow(flow_to_enter, current_step_id)

        # Check if we should exit current flow
        if self.current_flow and self.flow_context:
            exit_flows = should_exit_flow(self.flow_manager, current_step_id)
            if self.current_flow in exit_flows:
                self._exit_flow(current_step_id)

    def _enter_flow(self, flow: Flow, entry_step: str) -> None:
        """Enter a flow at the specified step."""
        try:
            # Get recent conversation history for flow context
            recent_history = (
                self.memory.get_history()[-10:] if self.memory.get_history() else []
            )
            previous_context = [
                msg for msg in recent_history if isinstance(msg, (Message, Summary))
            ]

            self.flow_context = flow.enter(
                entry_step=entry_step,
                previous_context=previous_context,
                metadata={
                    "session_id": self.session_id,
                    "entry_time": str(uuid.uuid4()),  # Simple timestamp alternative
                },
            )
            self.current_flow = flow
            log_debug(f"Entered flow '{flow.flow_id}' at step '{entry_step}'")

        except Exception as e:
            log_error(f"Failed to enter flow '{flow.flow_id}': {e}")

    def _exit_flow(self, exit_step: str) -> None:
        """Exit the current flow at the specified step."""
        if not self.current_flow or not self.flow_context:
            return

        try:
            exit_data = self.current_flow.exit(exit_step, self.flow_context)

            # Store flow summary in main memory if available
            if "memory" in exit_data and exit_data["memory"]:
                self.memory.add(exit_data["memory"])

            log_debug(
                f"Exited flow '{self.current_flow.flow_id}' at step '{exit_step}'"
            )

            self.current_flow = None
            self.flow_context = None

        except Exception as e:
            log_error(f"Failed to exit flow: {e}")
            # Clean up flow state even if exit fails
            if self.current_flow and self.flow_context:
                with contextlib.suppress(Exception):
                    self.current_flow.cleanup(self.flow_context)
            self.current_flow = None
            self.flow_context = None

    def _get_next_decision(self) -> BaseModel:
        """
        Get the next decision from the LLM based on the current step and history.

        :return: The decision made by the LLM.
        """
        route_decision_model = create_decision_model(
            current_step=self.current_step,
            current_step_tools=self._get_current_step_tools(),
        )

        # Get memory context - use flow memory if available, otherwise use session memory
        memory_context = self.memory.get_history()
        flow_memory_context = None

        if self.current_flow and self.flow_context:
            flow_memory = self.current_flow.get_memory()
            if flow_memory and isinstance(flow_memory, FlowMemoryComponent):
                flow_memory_context = flow_memory.memory.context

        remote_tools = self._get_remote_tools_for_step(self.current_step)
        decision = self.llm._get_output(
            steps=self.steps,
            current_step=self.current_step,
            tools=self.tools,
            history=flow_memory_context if flow_memory_context else memory_context,
            response_format=route_decision_model,
            system_message=self.system_message,
            persona=self.persona,
            remote_tools=remote_tools,
        )
        log_debug(f"Model decision: {decision}")
        return decision

    def next(
        self,
        user_input: Optional[str] = None,
        no_errors: int = 0,
        next_count: int = 0,
        return_tool: bool = False,
        return_step_transition: bool = False,
    ) -> tuple[BaseModel, Any]:
        """
        Advance the session to the next step based on user input and LLM decision.

        :param user_input: Optional user input string.
        :param no_errors: Number of consecutive errors encountered.
        :param next_count: Number of times the next function has been called.
        :param return_tool: Whether to return tool results.
        :param return_step_transition: Whether to return step transition.
        :return: A tuple containing the decision and any tool results.
        """
        if no_errors >= self.max_errors:
            raise ValueError(
                f"Maximum errors reached ({self.max_errors}). Stopping session."
            )
        if next_count >= self.max_iter:
            if not self.current_step.auto_flow:
                self._add_message(
                    "fallback",
                    (
                        "Maximum iterations reached. Inform the user and based on the "
                        "available context, produce a fallback response."
                    ),
                )
                return self.next()
            else:
                raise RecursionError(
                    f"Maximum iterations reached ({self.max_iter}). Stopping session."
                )

        log_debug(f"User input received: {user_input}")
        self._add_message("user", user_input) if user_input else None
        log_debug(f"Current step: {self.current_step.step_id}")

        # Check for flow transitions
        self._handle_flow_transitions()

        decision = self._get_next_decision()
        log_info(str(decision)) if self.verbose else log_debug(str(decision))
        log_debug(f"Action decided: {decision.action}")

        self._add_step_identifier(self.current_step.get_step_identifier())
        action = decision.action.value
        response = getattr(decision, "response", None)
        tool_call = getattr(decision, "tool_call", None)
        step_transition = getattr(decision, "step_transition", None)
        if action in [ACTION_ENUMS["ASK"], ACTION_ENUMS["ANSWER"]]:
            self._add_message(self.name, str(response))
            return decision, None
        elif action == ACTION_ENUMS["TOOL_CALL"]:
            _error: Optional[Exception] = None
            try:
                assert (
                    tool_call is not None and tool_call.__class__.__name__ == "ToolCall"
                ), "Expected ToolCall response"
                tool_name: str = tool_call.tool_name  # type: ignore
                tool_kwargs_model: BaseModel = tool_call.tool_kwargs  # type: ignore
                tool_kwargs: dict = tool_kwargs_model.model_dump()
                log_debug(f"Running tool: {tool_name} with args: {tool_kwargs}")
                try:
                    tool_results = self._run_tool(tool_name, tool_kwargs)
                    self._add_message(
                        "tool",
                        f"Tool {tool_name} executed successfully with args {tool_kwargs}.\nResults: {tool_results}",
                    )
                except Exception as e:
                    self._add_message(
                        "tool", f"Running tool {tool_name} with args {tool_kwargs}"
                    )
                    raise e
                log_info(f"Tool Results: {tool_results}") if self.verbose else None
            except FallbackError as e:
                _error = e
                self._add_message("fallback", str(e))
            except Exception as e:
                _error = e
                self._add_message("error", str(e))

            if return_tool and _error is None:
                return decision, tool_results
            return self.next(
                no_errors=no_errors + 1 if _error else 0,
                next_count=next_count + 1,
            )
        elif action == ACTION_ENUMS["MOVE"]:
            _error = None
            if step_transition in self.current_step.get_available_routes():
                # Check if we need to exit current flow before moving
                if self.current_flow and self.flow_context:
                    exit_flows = (
                        should_exit_flow(self.flow_manager, self.current_step.step_id)
                        if self.flow_manager
                        else []
                    )
                    if self.current_flow in exit_flows:
                        self._exit_flow(self.current_step.step_id)

                self.current_step = self.steps[step_transition]
                log_debug(f"Moving to next step: {self.current_step.step_id}")
                self._add_step_identifier(self.current_step.get_step_identifier())

                # Check if we need to enter a new flow after moving
                self._handle_flow_transitions()

            else:
                self._add_message(
                    "error",
                    f"Invalid route: {step_transition} not in {self.current_step.get_available_routes()}",
                )
                _error = ValueError(
                    f"Invalid route: {step_transition} not in {self.current_step.get_available_routes()}"
                )
            if return_step_transition:
                return decision, None
            return self.next(
                no_errors=no_errors + 1 if _error else 0,
                next_count=next_count + 1,
            )
        elif action == ACTION_ENUMS["END"]:
            # Clean up any active flows before ending
            if self.current_flow and self.flow_context:
                try:
                    self.current_flow.cleanup(self.flow_context)
                    log_debug(
                        f"Cleaned up flow '{self.current_flow.flow_id}' on session end"
                    )
                except Exception as e:
                    log_error(f"Error cleaning up flow on session end: {e}")
                finally:
                    self.current_flow = None
                    self.flow_context = None

            self._add_message("end", "Session ended.")
            return decision, None
        else:
            self._add_message(
                "error",
                f"Unknown action: {action}. Please check the action type.",
            )
            return self.next(
                no_errors=no_errors + 1,
                next_count=next_count + 1,
            )

    def _add_step_identifier(self, step_identifier: StepIdentifier) -> None:
        """
        Add a step identifier to the appropriate memory.

        :param step_identifier: The step identifier to add.
        """
        # If we're in a flow, only update flow memory
        if self.current_flow and self.flow_context:
            flow_memory = self.current_flow.get_memory()
            if flow_memory and isinstance(flow_memory, FlowMemoryComponent):
                flow_memory.add_to_context(step_identifier)
            # Don't update session memory while in flow
        else:
            # Only update session memory when not in a flow
            self.memory.add(step_identifier)

        log_debug(f"Step identifier added: {step_identifier.step_id}")

    def _get_remote_tools_for_step(self, step: Step) -> List[RemoteTool]:
        """
        Get the list of remote tools available in the given step.

        :param step: The Step object to check.
        :return: List of RemoteTool instances for remote tools.
        """
        remote_tools = []
        for tool_name in step.remote_tools:
            server_type, server_name, name = tool_name.split(":")
            if server_type == RemoteTool.RemoteToolType.mcp.value:
                mcp_server = self.mcp_servers.get(server_name)
                if not mcp_server:
                    log_error(
                        f"MCP server '{server_name}' not found for step '{step.step_id}'."
                    )
                    continue
                remote_tools.append(
                    RemoteTool.from_mcp_server(server=mcp_server, tool_name=name)
                )

        return remote_tools


class Agent:
    """Main interface for creating and managing Nomos Agents."""

    def __init__(
        self,
        llm: LLMBase,
        name: str,
        steps: List[Step],
        start_step_id: str,
        persona: Optional[str] = None,
        system_message: Optional[str] = None,
        tools: Optional[List[Union[Callable, str]]] = None,
        mcp_servers: Optional[List[MCPServer]] = None,
        show_steps_desc: bool = False,
        max_errors: int = 3,
        max_iter: int = 5,
        config: Optional[AgentConfig] = None,
    ) -> None:
        """
        Initialize an Agent.

        :param llm: LLMBase instance.
        :param name: Name of the agent.
        :param steps: List of Step objects.
        :param start_step_id: ID of the starting step.
        :param persona: Optional persona string.
        :param system_message: Optional system message.
        :param tools: List of tool callables.
        :param mcp_servers: List of MCPServer instances for tool discovery.
        :param show_steps_desc: Whether to show step descriptions.
        :param max_errors: Maximum consecutive errors before stopping or fallback. (Defaults to 3)
        :param max_iter: Maximum number of decision loops for single action. (Defaults to 5)
        :param config: Optional AgentConfig.
        """
        self.llm = llm
        self.name = name
        self.steps = {s.step_id: s for s in steps}
        self.start = start_step_id
        self.system_message = system_message
        self.persona = persona
        self.show_steps_desc = show_steps_desc
        self.max_errors = max_errors
        self.max_iter = max_iter
        tool_set = set(tools) if tools else set()
        self.mcp_servers: List[MCPServer] = mcp_servers or []

        for step in self.steps.values():
            _pkg_tools = [
                tool for tool in step.available_tools if is_package_tool(tool)
            ]
            tool_set.update(_pkg_tools)

        self.tools = list(tool_set)
        self.config = config

        # Initialize flow manager if flows are configured
        self.flow_manager: Optional[FlowManager] = None
        if config and config.flows:
            self.flow_manager = create_flows_from_config(config)
            log_debug(f"Agent initialized with {len(self.flow_manager.flows)} flows")

        # Validate start step ID
        if start_step_id not in self.steps:
            log_error(f"Start step ID {start_step_id} not found in steps")
            raise ValueError(f"Start step ID {start_step_id} not found in steps")
        # Validate step IDs in routes
        for step in self.steps.values():
            for route in step.routes:
                if route.target not in self.steps:
                    log_error(
                        f"Route target {route.target} not found in steps for step {step.step_id}"
                    )
                    raise ValueError(
                        f"Route target {route.target} not found in steps for step {step.step_id}"
                    )
        # Validate tool names
        for step in self.steps.values():
            for step_tool in step.available_tools:
                if is_remote_tool(step_tool):
                    mcp_server_name = step_tool.split(":")[1]
                    for mcp_server in self.mcp_servers:
                        if mcp_server.name == mcp_server_name:
                            break
                    else:
                        log_error(
                            f"MCP server {mcp_server_name} not found for step {step.step_id}"
                        )
                        raise ValueError(
                            f"MCP server {mcp_server_name} not found for step {step.step_id}"
                        )
                else:
                    for tool in self.tools:
                        if (callable(tool) and tool.__name__ == step_tool) or (
                            isinstance(tool, str) and tool == step_tool
                        ):
                            break
                    else:
                        log_error(
                            f"Tool {step_tool} not found in tools for step {step.step_id}"
                        )
                        raise ValueError(
                            f"Tool {step_tool} not found in tools for step {step.step_id}"
                        )
        log_debug(f"FlowManager initialized with start step '{start_step_id}'")

    @classmethod
    def from_config(
        cls,
        config: AgentConfig,
        llm: Optional[LLMBase] = None,
        tools: Optional[List[Union[Callable, str]]] = None,
    ) -> "Agent":
        """
        Create an Agent from an AgentConfig object.

        :param llm: LLMBase instance.
        :param config: AgentConfig instance.
        :param tools: List of tool callables.
        :param mcp_servers: List of MCPServer instances for tool discovery.
        :return: Nomos instance.
        """
        if not llm:
            if not config.llm:
                raise ValueError(
                    "No LLM provided. Please provide an LLM or a config with an LLM."
                )
            llm = config.llm.get_llm()

        return cls(
            llm=llm,
            name=config.name,
            steps=config.steps,
            start_step_id=config.start_step_id,
            system_message=config.system_message,
            persona=config.persona,
            tools=tools or [],
            mcp_servers=config.mcp_servers,
            show_steps_desc=config.show_steps_desc,
            max_errors=config.max_errors,
            max_iter=config.max_iter,
            config=config,
        )

    def create_session(
        self, memory: Optional[Memory] = None, verbose: bool = False
    ) -> Session:
        """
        Create a new Session for this agent.

        :param memory: Optional Memory instance.
        :param verbose: Whether to return verbose output.
        :return: Session instance.
        """
        log_debug("Creating new session")
        if not memory:
            memory = (
                self.config.memory.get_memory()
                if self.config and self.config.memory
                else Memory()
            )

        return Session(
            name=self.name,
            llm=self.llm,
            memory=memory,
            steps=self.steps,
            start_step_id=self.start,
            system_message=self.system_message,
            persona=self.persona,
            tools=self.tools,
            mcp_servers=self.mcp_servers,
            show_steps_desc=self.show_steps_desc,
            max_errors=self.max_errors,
            max_iter=self.max_iter,
            verbose=verbose,
            config=self.config,
        )

    def load_session(self, session_id: str) -> Session:
        """
        Load a Session by session_id.

        :param session_id: The session ID string.
        :return: Loaded Session instance.
        """
        log_debug(f"Loading session {session_id}")
        return Session.load_session(session_id)

    def get_session_from_dict(self, session_data: dict) -> Session:
        """
        Create a Session from a dictionary.

        :param session_data: Dictionary containing session data.
        :return: Session instance.
        """
        log_debug(f"Creating session from dict: {session_data}")

        # Convert the History items into list of Message or Step
        new_session_data = session_data.copy()
        new_session_data["history"] = []
        for history_item in session_data.get("history", []):
            if isinstance(history_item, dict):
                if "role" in history_item:
                    new_session_data["history"].append(Message(**history_item))
                elif "step_id" in history_item:
                    new_session_data["history"].append(StepIdentifier(**history_item))
                elif "content" in history_item:
                    new_session_data["history"].append(Summary(**history_item))
            else:
                raise ValueError(
                    f"Invalid history item: {history_item}. Must be a dict."
                )

        memory = (
            self.config.memory.get_memory()
            if self.config and self.config.memory
            else Memory()
        )

        session = Session(
            name=self.name,
            llm=self.llm,
            memory=memory,
            tools=self.tools,
            mcp_servers=self.mcp_servers,
            config=self.config,
            persona=self.persona,
            steps=self.steps,
            start_step_id=self.start,
            system_message=self.system_message,
            show_steps_desc=self.show_steps_desc,
            max_errors=self.max_errors,
            max_iter=self.max_iter,
            **new_session_data,
        )

        # Restore flow state if present
        if "flow_state" in session_data and session.flow_manager:
            flow_state = session_data["flow_state"]
            flow_id = flow_state.get("flow_id")
            flow_context_data = flow_state.get("flow_context")

            if flow_id in session.flow_manager.flows and flow_context_data:
                from .models.flow import FlowContext

                session.current_flow = session.flow_manager.flows[flow_id]
                session.flow_context = FlowContext(**flow_context_data)
                log_debug(f"Restored flow state for flow '{flow_id}'")

        return session

    def next(
        self,
        user_input: Optional[str] = None,
        session_data: Optional[dict] = None,
        verbose: bool = False,
    ) -> tuple[BaseModel, str, dict]:
        """
        Advance the session to the next step based on user input and LLM decision.

        :param user_input: Optional user input string.
        :param session_data: Optional session data dictionary.
        :param verbose: Whether to return verbose output.
        :return: A tuple containing the decision and session data.
        """
        session = (
            self.get_session_from_dict(session_data)
            if session_data
            else self.create_session()
        )
        decision, tool_output = session.next(
            user_input=user_input, return_tool=verbose, return_step_transition=verbose
        )
        return decision, tool_output, session.to_dict()


__all__ = ["Session", "Agent"]
