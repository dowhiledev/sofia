"""Tests for Flow construct functionality."""

from typing import Any, Dict
from unittest.mock import Mock, patch

import pytest

from nomos.config import AgentConfig
from nomos.memory.flow import FlowMemoryComponent
from nomos.models.agent import Event, Step
from nomos.models.flow import Flow, FlowComponent, FlowConfig, FlowContext, FlowManager
from nomos.utils import flow_utils


class MockFlowComponent(FlowComponent):
    """Mock flow component for testing."""

    def __init__(self):
        self.entered = False
        self.exited = False
        self.cleaned_up = False
        self.exit_data = {"mock": "data"}

    def enter(self, context: FlowContext) -> None:
        self.entered = True
        self.enter_context = context

    def exit(self, context: FlowContext) -> Dict[str, Any]:
        self.exited = True
        self.exit_context = context
        return self.exit_data

    def cleanup(self, context: FlowContext) -> None:
        self.cleaned_up = True
        self.cleanup_context = context


class TestFlowContext:
    """Test FlowContext model."""

    def test_flow_context_creation(self):
        """Test creating a FlowContext."""
        context = FlowContext(flow_id="test_flow", entry_step="step1", metadata={"test": "value"})

        assert context.flow_id == "test_flow"
        assert context.entry_step == "step1"
        assert context.previous_context is None
        assert context.metadata == {"test": "value"}

    def test_flow_context_with_previous_context(self):
        """Test FlowContext with previous context."""
        messages = [Event(type="user", content="Hello")]
        context = FlowContext(flow_id="test_flow", entry_step="step1", previous_context=messages)

        assert context.previous_context == messages


class TestFlowConfig:
    """Test FlowConfig model."""

    def test_flow_config_creation(self):
        """Test creating a FlowConfig."""
        config = FlowConfig(
            flow_id="test_flow",
            enters=["step1", "step2"],
            exits=["step3", "step4"],
            description="Test flow",
            components={"memory": {"llm": {"provider": "openai", "model": "gpt-4o-mini"}}},
        )

        assert config.flow_id == "test_flow"
        assert config.enters == ["step1", "step2"]
        assert config.exits == ["step3", "step4"]
        assert config.description == "Test flow"
        assert "memory" in config.components


class TestFlow:
    """Test Flow class."""

    def setup_method(self):
        """Set up test fixtures."""
        self.config = FlowConfig(
            flow_id="test_flow", enters=["step1"], exits=["step3"], components={}
        )

        self.steps = [
            Step(step_id="step1", description="First step"),
            Step(step_id="step2", description="Second step"),
            Step(step_id="step3", description="Third step"),
        ]

        self.mock_component = MockFlowComponent()
        self.component_registry = {"mock": lambda: self.mock_component}

    def test_flow_creation(self):
        """Test creating a Flow."""
        flow = Flow(
            config=self.config,
            steps=self.steps,
            component_registry=self.component_registry,
        )

        assert flow.flow_id == "test_flow"
        assert flow.entry_steps == {"step1"}
        assert flow.exit_steps == {"step3"}
        assert len(flow.steps) == 3
        assert "step1" in flow.steps
        assert "step2" in flow.steps
        assert "step3" in flow.steps

    def test_flow_with_components(self):
        """Test Flow with components."""
        self.config.components = {"mock": {}}
        flow = Flow(
            config=self.config,
            steps=self.steps,
            component_registry=self.component_registry,
        )

        assert "mock" in flow.components
        assert isinstance(flow.components["mock"], MockFlowComponent)

    def test_can_enter(self):
        """Test can_enter method."""
        flow = Flow(config=self.config, steps=self.steps)

        assert flow.can_enter("step1") is True
        assert flow.can_enter("step2") is False
        assert flow.can_enter("step3") is False

    def test_can_exit(self):
        """Test can_exit method."""
        flow = Flow(config=self.config, steps=self.steps)

        assert flow.can_exit("step1") is False
        assert flow.can_exit("step2") is False
        assert flow.can_exit("step3") is True

    def test_contains_step(self):
        """Test contains_step method."""
        flow = Flow(config=self.config, steps=self.steps)

        assert flow.contains_step("step1") is True
        assert flow.contains_step("step2") is True
        assert flow.contains_step("step3") is True
        assert flow.contains_step("step4") is False

    def test_enter_flow(self):
        """Test entering a flow."""
        self.config.components = {"mock": {}}
        flow = Flow(
            config=self.config,
            steps=self.steps,
            component_registry=self.component_registry,
        )

        context = flow.enter("step1")

        assert context.flow_id == "test_flow"
        assert context.entry_step == "step1"
        assert self.mock_component.entered is True
        assert self.mock_component.enter_context == context

        # Check active contexts
        context_key = f"{context.flow_id}:{context.entry_step}"
        assert context_key in flow.active_contexts

    def test_enter_invalid_step(self):
        """Test entering flow with invalid step."""
        flow = Flow(config=self.config, steps=self.steps)

        with pytest.raises(ValueError, match="not a valid entry point"):
            flow.enter("step2")

    def test_exit_flow(self):
        """Test exiting a flow."""
        self.config.components = {"mock": {}}
        flow = Flow(
            config=self.config,
            steps=self.steps,
            component_registry=self.component_registry,
        )

        context = flow.enter("step1")
        exit_data = flow.exit("step3", context)

        assert self.mock_component.exited is True
        assert exit_data == {"mock": {"mock": "data"}}

        # Check context cleanup
        context_key = f"{context.flow_id}:{context.entry_step}"
        assert context_key not in flow.active_contexts

    def test_exit_invalid_step(self):
        """Test exiting flow with invalid step."""
        flow = Flow(config=self.config, steps=self.steps)
        context = flow.enter("step1")

        with pytest.raises(ValueError, match="not a valid exit point"):
            flow.exit("step2", context)

    def test_cleanup_flow(self):
        """Test cleaning up a flow."""
        self.config.components = {"mock": {}}
        flow = Flow(
            config=self.config,
            steps=self.steps,
            component_registry=self.component_registry,
        )

        context = flow.enter("step1")
        flow.cleanup(context)

        assert self.mock_component.cleaned_up is True

        # Check context cleanup
        context_key = f"{context.flow_id}:{context.entry_step}"
        assert context_key not in flow.active_contexts

    def test_get_component(self):
        """Test getting a component."""
        self.config.components = {"mock": {}}
        flow = Flow(
            config=self.config,
            steps=self.steps,
            component_registry=self.component_registry,
        )

        component = flow.get_component("mock")
        assert component is self.mock_component

        non_existent = flow.get_component("non_existent")
        assert non_existent is None

    def test_get_memory(self):
        """Test getting memory component."""
        self.config.components = {"memory": {}}
        memory_component = MockFlowComponent()
        registry = {"memory": lambda: memory_component}

        flow = Flow(config=self.config, steps=self.steps, component_registry=registry)

        memory = flow.get_memory()
        assert memory is memory_component


class TestFlowManager:
    """Test FlowManager class."""

    def setup_method(self):
        """Set up test fixtures."""
        self.manager = FlowManager()

        # Create test flows
        self.flow1_config = FlowConfig(flow_id="flow1", enters=["step1"], exits=["step2"])
        self.flow1_steps = [
            Step(step_id="step1", description="Step 1"),
            Step(step_id="step2", description="Step 2"),
        ]
        self.flow1 = Flow(config=self.flow1_config, steps=self.flow1_steps)

        self.flow2_config = FlowConfig(flow_id="flow2", enters=["step2"], exits=["step3"])
        self.flow2_steps = [
            Step(step_id="step2", description="Step 2"),
            Step(step_id="step3", description="Step 3"),
        ]
        self.flow2 = Flow(config=self.flow2_config, steps=self.flow2_steps)

    def test_register_flow(self):
        """Test registering a flow."""
        self.manager.register_flow(self.flow1)

        assert "flow1" in self.manager.flows
        assert self.manager.flows["flow1"] is self.flow1

        # Check step-to-flows mapping
        assert "step1" in self.manager.step_to_flows
        assert "step2" in self.manager.step_to_flows
        assert "flow1" in self.manager.step_to_flows["step1"]
        assert "flow1" in self.manager.step_to_flows["step2"]

    def test_get_flows_for_step(self):
        """Test getting flows for a step."""
        self.manager.register_flow(self.flow1)
        self.manager.register_flow(self.flow2)

        flows_for_step1 = self.manager.get_flows_for_step("step1")
        assert len(flows_for_step1) == 1
        assert flows_for_step1[0] is self.flow1

        flows_for_step2 = self.manager.get_flows_for_step("step2")
        assert len(flows_for_step2) == 2
        assert self.flow1 in flows_for_step2
        assert self.flow2 in flows_for_step2

    def test_find_entry_flows(self):
        """Test finding entry flows."""
        self.manager.register_flow(self.flow1)
        self.manager.register_flow(self.flow2)

        entry_flows_step1 = self.manager.find_entry_flows("step1")
        assert len(entry_flows_step1) == 1
        assert entry_flows_step1[0] is self.flow1

        entry_flows_step2 = self.manager.find_entry_flows("step2")
        assert len(entry_flows_step2) == 1
        assert entry_flows_step2[0] is self.flow2

    def test_find_exit_flows(self):
        """Test finding exit flows."""
        self.manager.register_flow(self.flow1)
        self.manager.register_flow(self.flow2)

        exit_flows_step2 = self.manager.find_exit_flows("step2")
        assert len(exit_flows_step2) == 1
        assert exit_flows_step2[0] is self.flow1

        exit_flows_step3 = self.manager.find_exit_flows("step3")
        assert len(exit_flows_step3) == 1
        assert exit_flows_step3[0] is self.flow2

    def test_transition_between_flows(self):
        """Test transitioning between flows."""
        # Set up flows with mock components
        mock_component1 = MockFlowComponent()
        mock_component2 = MockFlowComponent()

        self.flow1_config.components = {"mock": {}}
        self.flow2_config.components = {"mock": {}}

        registry = {"mock": lambda: mock_component1}
        flow1 = Flow(
            config=self.flow1_config,
            steps=self.flow1_steps,
            component_registry=registry,
        )

        registry2 = {"mock": lambda: mock_component2}
        flow2 = Flow(
            config=self.flow2_config,
            steps=self.flow2_steps,
            component_registry=registry2,
        )

        self.manager.register_flow(flow1)
        self.manager.register_flow(flow2)

        # Enter first flow
        context1 = flow1.enter("step1")

        # Transition to second flow
        new_context = self.manager.transition_between_flows(flow1, flow2, "step2", context1)

        # Check that first flow was exited
        assert mock_component1.exited is True

        # Check that second flow was entered
        assert mock_component2.entered is True
        assert new_context.flow_id == "flow2"
        assert new_context.entry_step == "step2"
        assert "previous_flow_data" in new_context.metadata


class TestFlowMemoryComponent:
    """Test FlowMemoryComponent integration."""

    @patch("nomos.memory.flow.FlowMemory")
    def test_flow_memory_component_creation(self, mock_flow_memory):
        """Test creating FlowMemoryComponent."""
        component = FlowMemoryComponent()

        assert hasattr(component, "memory")
        mock_flow_memory.assert_called_once()

    @patch("nomos.memory.flow.FlowMemory")
    def test_flow_memory_component_lifecycle(self, mock_flow_memory):
        """Test FlowMemoryComponent lifecycle methods."""
        mock_memory_instance = Mock()
        mock_flow_memory.return_value = mock_memory_instance

        component = FlowMemoryComponent()
        context = FlowContext(flow_id="test", entry_step="step1")

        # Test enter
        component.enter(context)
        mock_memory_instance._enter.assert_called_once_with(context.previous_context)

        # Test exit
        mock_summary = Mock()
        mock_memory_instance._exit.return_value = mock_summary
        result = component.exit(context)
        mock_memory_instance._exit.assert_called_once()
        assert result is mock_summary

        # Test cleanup
        component.cleanup(context)
        mock_memory_instance.context.clear.assert_called_once()


class TestFlowUtils:
    """Test flow_utils helper functions."""

    def _build_config(self):
        steps = [
            Step(step_id="s1", description="step 1"),
            Step(step_id="s2", description="step 2"),
            Step(step_id="s3", description="step 3"),
        ]
        flows = [
            FlowConfig(flow_id="f1", enters=["s1"], exits=["s2"]),
            FlowConfig(flow_id="f2", enters=["s2"], exits=["s3"]),
        ]
        return AgentConfig(name="a", steps=steps, start_step_id="s1", flows=flows)

    def test_create_flows_from_config(self):
        config = self._build_config()
        manager = flow_utils.create_flows_from_config(config)

        assert len(manager.flows) == 2
        assert "f1" in manager.flows and "f2" in manager.flows
        # step flow_id gets updated to the last flow it belongs to
        assert config.steps[1].flow_id == "f2"

    def test_should_enter_and_exit_flow(self):
        manager = flow_utils.create_flows_from_config(self._build_config())

        enter_flows = flow_utils.should_enter_flow(manager, "s1")
        assert [f.flow_id for f in enter_flows] == ["f1"]

        exit_flows = flow_utils.should_exit_flow(manager, "s2")
        assert [f.flow_id for f in exit_flows] == ["f1"]

    def test_get_flow_for_step(self):
        manager = flow_utils.create_flows_from_config(self._build_config())

        flow = flow_utils.get_flow_for_step(manager, "s2")
        assert flow.flow_id == "f1"


if __name__ == "__main__":
    pytest.main([__file__])
