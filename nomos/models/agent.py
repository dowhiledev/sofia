"""Flow models for Nomos's decision-making process."""

from enum import Enum
from typing import Any, Dict, List, Literal, Optional, Type, Union

from pydantic import BaseModel, Field

from .tool import Tool, is_package_tool, is_remote_tool
from ..constants import ACTION_ENUMS
from ..utils.utils import create_base_model, create_enum

Action = create_enum("Action", ACTION_ENUMS)


class Route(BaseModel):
    """
    Represents a route (transition) from one step to another in the flow.

    Attributes:
        target (str): The target step ID.
        condition (str): The condition for taking this route.
    """

    target: str = Field(
        ...,
        description="Target step ID to move to when this route is taken.",
    )
    condition: str = Field(
        ...,
        description="Condition that must be met to take this route.",
    )

    def __str__(self) -> str:
        """Return a string representation of the route."""
        return f"- if '{self.condition}' then -> {self.target}"


class StepIdentifier(BaseModel):
    """
    Represents a step identifier in the flow.

    Attributes:
        step_id (str): Unique identifier for the step.
    """

    step_id: str


class Step(BaseModel):
    """
    Represents a step in the agent's flow.

    Attributes:
        step_id (str): Unique identifier for the step.
        description (str): Description of the step.
        routes (List[Route]): List of possible routes from this step.
        available_tools (List[str]): List of tool names available in this step.
        tools (List[Tool]): List of Tool objects available in this step.
        answer_model (Optional[Dict[str, Dict[str, Any]]]): Pydantic model for the agent's answer structure.
        auto_flow (bool): Flag indicating if the step should automatically flow without additonal inputs or answering.
        provide_suggestions (bool): Flag indicating if the step should provide suggestions to the user.
    Methods:
        get_available_routes() -> List[str]: Get the list of available route targets.
    """

    step_id: str
    description: str
    routes: List[Route] = []
    available_tools: List[str] = []
    answer_model: Optional[Union[Dict[str, Dict[str, Any]], BaseModel]] = None
    auto_flow: bool = False
    quick_suggestions: bool = False
    flow_id: Optional[str] = None  # Add this to associate steps with flows

    def model_post_init(self, __context) -> None:
        """Validate that auto_flow steps have at least one tool or route."""
        if self.auto_flow and not (self.routes or self.available_tools):
            raise ValueError(
                f"Step '{self.step_id}': When auto_flow is True, at least one tool or route must be available"
            )
        if self.auto_flow and self.quick_suggestions:
            raise ValueError(
                f"Step '{self.step_id}': When auto_flow is True, quick_suggestions cannot be True"
            )

    def get_answer_model(self) -> BaseModel:
        """
        Get the Pydantic model for the agent's answer structure.

        :return: Pydantic model for the answer structure.
        """
        if isinstance(self.answer_model, dict):
            return create_base_model("AnswerModel", self.answer_model)
        elif isinstance(self.answer_model, BaseModel):
            return self.answer_model
        else:
            raise ValueError(
                f"Step '{self.step_id}': answer_model must be a dictionary or a Pydantic model"
            )

    def get_available_routes(self) -> List[str]:
        """
        Get the list of available route targets from this step.

        :return: List of target step IDs.
        """
        return [route.target for route in self.routes]

    @property
    def tool_ids(self) -> List[str]:
        """
        Get the list of available tool names from this step.

        :return: List of tool names.
        """
        return [
            Tool.from_pkg(tool).name if is_package_tool(tool) else tool
            for tool in filter(lambda t: not is_remote_tool(t), self.available_tools)
        ]

    @property
    def remote_tools(self) -> List[str]:
        """
        Get the list of available remote tool names for this step.

        :return: List of tool names.
        """
        remote_tools = list(filter(lambda t: is_remote_tool(t), self.available_tools))
        return remote_tools

    def get_step_identifier(self) -> StepIdentifier:
        """
        Get the step identifier for this step.

        :return: StepIdentifier object.
        """
        return StepIdentifier(step_id=self.step_id)

    def __str__(self) -> str:
        """Return a string representation of the step."""
        return f"[Step] {self.step_id}: {self.description}"


class Message(BaseModel):
    """
    Represents a message in the conversation history.

    Attributes:
        role (str): The role of the message sender (e.g., 'user', 'assistant', 'tool').
        content (str): The message content.
    """

    role: Union[Literal["user", "tool", "error", "fallback"], str]
    content: str

    def __str__(self) -> str:
        """Return a string representation of the message."""
        return f"[{self.role.title()}] {self.content}"


class Summary(BaseModel):
    """Summary of a list of messages."""

    summary: List[str] = Field(
        ..., description="Detailed summary of the Context. (Min 5 items)"
    )

    @property
    def content(self) -> str:
        """Get the summary content as a single string (markdown list)."""
        return "\n".join(f"- {item}" for item in self.summary if item.strip())

    def __str__(self) -> str:
        """Return a string representation of the summary."""
        return f"[Past Summary] {self.content}"


def create_decision_model(
    current_step: Step, current_step_tools: List[Tool]
) -> Type[BaseModel]:
    """
    Dynamically create a Pydantic model for route/tool decision output.

    :param available_step_ids: List of available step IDs for routing.
    :param tool_ids: List of available tool names.
    :param tool_models: List of Pydantic models for tool arguments.
    :return: A dynamically created Pydantic BaseModel for the decision.
    """
    available_step_ids = current_step.get_available_routes()
    tool_ids = [tool.name for tool in current_step_tools]
    tool_models = [tool.get_args_model() for tool in current_step_tools]
    action_ids = (
        (["ASK", "ANSWER", "END"] if not current_step.auto_flow else ["END"])
        + (["MOVE"] if available_step_ids else [])
        + (["TOOL_CALL"] if tool_ids else [])
    )
    ActionEnum = create_action_enum(action_ids)  # noqa

    params = {
        "reasoning": {
            "type": List[str],
            "description": "Step by Step Reasoning to Decide",
        },
        "action": {"type": ActionEnum, "description": "Next Action"},
    }

    if not current_step.auto_flow:
        if current_step.answer_model:
            answer_model = current_step.get_answer_model()
            response_type = Union.__getitem__((str, answer_model))
            response_desc = (
                f"Response as string if ASK or {answer_model.__name__} if ANSWER."
            )
        else:
            response_type = str
            response_desc = "Response (String) if ASK or ANSWER."
        params["response"] = {
            "type": response_type,
            "description": response_desc,
            "optional": True,
            "default": None,
        }
        if current_step.quick_suggestions:
            params["suggestions"] = {
                "type": List[str],
                "description": "Quick User Input Suggestions for the User to Choose if ASK.",
                "optional": True,
                "default": None,
            }

    if len(available_step_ids) > 0:
        params["step_transition"] = {
            "type": Literal.__getitem__(tuple(available_step_ids)),
            "description": "Step Id (String) if MOVE.",
            "optional": True,
            "default": None,
        }

    if len(tool_ids) > 0 and len(tool_models) > 0:
        tool_call_model = create_base_model(
            "ToolCall",
            {
                "tool_name": {
                    "type": Literal.__getitem__(tuple(tool_ids)),
                    "description": "Tool name for TOOL_CALL.",
                },
                "tool_kwargs": {
                    "type": (
                        tool_models[0]
                        if len(tool_models) == 1
                        else Union.__getitem__(tuple(tool_models))
                    ),
                    "description": "Corresponding Tool arguments for TOOL_CALL.",
                },
            },
        )
        params["tool_call"] = {
            "type": tool_call_model,
            "description": "Tool Call (ToolCall) if TOOL_CALL.",
            "optional": True,
            "default": None,
        }

    assert len(params) > 2, "Something went wrong, Please check the step configuration."

    return create_base_model(
        "Decision",
        params,
    )


def create_action_enum(actions: List[str]) -> Enum:
    """
    Dynamically create an Enum class for actions.

    :param name: Name of the enum.
    :param actions: Dictionary of action names to values.
    :return: A dynamically created Enum class.
    """
    actions_dict = {
        action: ACTION_ENUMS[action] for action in actions if action in ACTION_ENUMS
    }
    return create_enum("Action", actions_dict)


__all__ = [
    "Action",
    "Route",
    "Step",
    "Message",
    "Summary",
    "create_decision_model",
]
