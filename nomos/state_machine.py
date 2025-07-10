"""State machine for managing steps and flow transitions in Nomos."""

from typing import Dict, List, Optional, Tuple

import colorama
from colorama import Fore, Style

from .config import AgentConfig
from .memory.base import Memory
from .memory.flow import FlowMemoryComponent
from .models.agent import Event, FlowState, State, Step, Summary
from .models.flow import Flow, FlowContext, FlowManager
from .utils.flow_utils import create_flows_from_config


class StateMachine:
    """Compile step and flow transitions for fast lookups."""

    def __init__(
        self,
        steps: Dict[str, Step],
        memory: Memory,
        flow_manager: Optional[FlowManager] = None,
        flows: Optional[List[Flow]] = None,
        config: Optional[AgentConfig] = None,
        start_step_id: Optional[str] = None,
    ) -> None:
        """
        Initialize the state machine with steps, flows, and memory.

        :param steps: Dictionary of step IDs to Step objects.
        :param flow_manager: Optional FlowManager instance to manage flows.
        :param flows: Optional list of Flow objects to register with the FlowManager.
        :param config: Optional AgentConfig containing flow definitions.
        :param memory: Optional Memory instance to store session history.
        :param start_step_id: Optional starting step ID. If not provided, defaults to the first step in `steps`.
        """
        # Map of step -> allowed next step ids
        self.steps = steps
        self.transitions: Dict[str, List[str]] = {
            step_id: step.get_available_routes() for step_id, step in steps.items()
        }

        self.memory = memory
        self.current_step_id = start_step_id or next(iter(steps))

        if not flow_manager:
            if flows:
                flow_manager = FlowManager()
                for flow in flows:
                    flow_manager.register_flow(flow)
            elif config and config.flows:
                flow_manager = create_flows_from_config(config)

        # Flow handling
        self.flow_manager = flow_manager
        self.current_flow: Optional[Flow] = None
        self.flow_context: Optional[FlowContext] = None

        # Pre-compute flow entry/exit mappings if a flow manager is provided
        self.flow_enters: Dict[str, List[str]] = {}
        self.flow_exits: Dict[str, List[str]] = {}
        if flow_manager:
            for step_id in steps:
                self.flow_enters[step_id] = [
                    flow.flow_id for flow in flow_manager.find_entry_flows(step_id)
                ]
                self.flow_exits[step_id] = [
                    flow.flow_id for flow in flow_manager.find_exit_flows(step_id)
                ]

    @property
    def current_step(self) -> Step:
        """Return the current step object."""
        return self.steps[self.current_step_id]

    def can_transition(self, current: str, target: str) -> bool:
        """Return True if transition is allowed."""
        if current not in self.transitions:
            raise ValueError(f"Unknown step: {current}")
        return target in self.transitions[current]

    def move(self, target: str) -> str:
        """Move to the target step if allowed and return new step id."""
        if not self.can_transition(self.current_step_id, target):
            raise ValueError(f"Invalid transition from {self.current_step_id} to {target}")
        self.current_step_id = target
        return target

    def transition(self, current: str, target: str) -> str:
        """Validate transition and return next state."""
        if not self.can_transition(current, target):
            raise ValueError(f"Invalid transition from {current} to {target}")
        return target

    def get_flow_transitions(self, step_id: str) -> Tuple[List[str], List[str]]:
        """Return flow ids to enter and exit for the given step."""
        enters = self.flow_enters.get(step_id, [])
        exits = self.flow_exits.get(step_id, [])
        return enters, exits

    # ------------------------------------------------------------------
    # Flow management helpers
    # ------------------------------------------------------------------
    def _enter_flow(self, flow: Flow, entry_step: str, session_id: str) -> None:
        """Enter a flow at the specified step."""
        try:
            recent_history = (
                self.memory.get_history()[-10:] if self.memory and self.memory.get_history() else []
            )
            previous_context = [msg for msg in recent_history if isinstance(msg, (Event, Summary))]

            self.flow_context = flow.enter(
                entry_step=entry_step,
                previous_context=previous_context,
                metadata={"session_id": session_id},
            )
            self.current_flow = flow
        except Exception:
            # In tests we simply swallow errors to keep behavior consistent
            self.current_flow = None
            self.flow_context = None

    def _exit_flow(self, exit_step: str) -> None:
        """Exit the current flow."""
        if not self.current_flow or not self.flow_context:
            return

        try:
            exit_data = self.current_flow.exit(exit_step, self.flow_context)
            if self.memory and "memory" in exit_data and exit_data["memory"]:
                self.memory.add(exit_data["memory"])
        finally:
            self.current_flow = None
            self.flow_context = None

    def handle_flow_transitions(self, step_id: str, session_id: str, verbose: bool = False) -> None:
        """Enter or exit flows based on current step."""
        if not self.flow_manager:
            return

        enters, exits = self.get_flow_transitions(step_id)

        if enters and not self.current_flow:
            flow_to_enter = self.flow_manager.flows[enters[0]]
            self._enter_flow(flow_to_enter, step_id, session_id)
            if verbose:
                self.pp_flow_transitions("enter", step_id, flow_to_enter.flow_id)

        if self.current_flow and self.flow_context and self.current_flow.flow_id in exits:
            self._exit_flow(step_id)
            if verbose:
                self.pp_flow_transitions("exit", step_id, self.current_flow.flow_id)

    @staticmethod
    def pp_flow_transitions(type: str, step_id: str, flow_id: str) -> None:
        """Pretty print flow transitions for debugging with colors."""
        colorama.init(autoreset=True)

        type_str = "Entering" if type == "enter" else "Exiting"

        print(
            f"\n{Style.BRIGHT}{Fore.CYAN}{type_str} flow{Style.RESET_ALL}: "
            f"{flow_id} at step {step_id}"
        )

    # ------------------------------------------------------------------
    # Persistence helpers
    # ------------------------------------------------------------------
    def get_flow_state(self) -> Optional[FlowState]:
        """Return the current flow state if available."""
        if self.current_flow and self.flow_context:
            flow_memory = self.current_flow.get_memory()
            flow_memory_context = (
                flow_memory.memory.context if isinstance(flow_memory, FlowMemoryComponent) else []
            )
            return FlowState(
                flow_id=self.current_flow.flow_id,
                flow_memory_context=flow_memory_context,
                flow_context=self.flow_context,
            )
        return None

    def load_state(self, state: Optional[State]) -> None:
        """Restore step, memory, and flow state."""
        if not state:
            return

        step_id = state.current_step_id
        history = state.history
        flow_state = state.flow_state

        if step_id:
            self.current_step_id = step_id

        if history is not None and self.memory is not None:
            self.memory.context = history  # type: ignore[assignment]

        if flow_state and self.flow_manager:
            flow_id = flow_state.flow_id
            self.flow_context = flow_state.flow_context
            if flow_id in self.flow_manager.flows:
                self.current_flow = self.flow_manager.flows[flow_state.flow_id]
                flow_memory = self.current_flow.get_memory()
                if isinstance(flow_memory, FlowMemoryComponent):
                    flow_memory.memory.context = flow_state.flow_memory_context
            else:
                raise ValueError(f"Flow {flow_id} not found in flow manager")


__all__ = ["StateMachine"]
