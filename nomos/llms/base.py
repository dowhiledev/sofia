"""LLMBase class for SOFIA agent framework."""

from typing import Any, Dict, List, Optional, Union

from pydantic import BaseModel

from ..constants import DEFAULT_PERSONA, DEFAULT_SYSTEM_MESSAGE
from ..models.agent import Message, Step, StepIdentifier, Summary
from ..models.tool import RemoteTool, Tool
from ..utils.logging import log_error


class LLMBase:
    """Abstract base class for LLM integrations in SOFIA."""

    __provider__: str = "base"

    def __init__(self) -> None:
        """Initialize the LLMBase class."""
        raise NotImplementedError("Subclasses should implement this method.")

    @staticmethod
    def get_routes_desc(current_step: Step) -> str:
        """
        Get a string description of available routes from the current step.

        :param current_step: The current step.
        :return: String description of routes.
        """
        routes_desc = [str(route) for route in current_step.routes]
        return "\n".join(routes_desc)

    @staticmethod
    def get_tools_desc(tools: Dict[str, Tool], available_tools: List[str]) -> str:
        """
        Get a string description of available tools for the current step.

        :param tools: Dictionary of tool name to Tool.
        :param available_tools: List of tool names available in this step.
        :return: String description of tools.
        """
        tools_desc = []
        for tool_name in available_tools:
            tool = tools.get(tool_name)
            if not tool:
                log_error(f"Tool '{tool_name}' not found in session tools. Skipping.")
                continue
            tools_desc.append(f"- {str(tool)}")
        return "\n".join(tools_desc)

    @staticmethod
    def format_history(
        history: List[Union[Message, Step, Summary]], max_errors: int = 3
    ) -> str:
        """
        Format the chat history for display or LLM input.

        :param history: List of Message or Step objects.
        :param max_errors: Maximum number of consecutive errors to display.
        :return: String representation of the history.
        """
        history_str = []
        # log_debug(f"Formatting chat history: {history}")
        n_last_consecutive_errors = 0
        for item in history:
            if isinstance(item, Message):
                if item.role == "error":
                    n_last_consecutive_errors += 1
                else:
                    n_last_consecutive_errors = 0
            elif isinstance(item, Step):
                n_last_consecutive_errors = 0
        if n_last_consecutive_errors > max_errors:
            log_error(
                f"Too many consecutive errors in history. Only showing the last {max_errors} errors out of  {n_last_consecutive_errors}"
            )
        for i, item in enumerate(history):
            # If the error message is not within the last max_errors, skip it
            if (
                isinstance(item, Message)
                and item.role == "error"
                and n_last_consecutive_errors > max_errors
                and i < len(history) - max_errors
            ):
                continue
            # If the fallback message is not the last one in the history, skip it
            if (
                isinstance(item, Message)
                and item.role == "fallback"
                and i < len(history) - 1
            ):
                continue
            history_str.append(str(item))
        return "\n".join(history_str)

    def get_messages(
        self,
        current_step: Step,
        tools: Dict[str, Tool],
        history: List[Union[Message, Step, Summary]],
        system_message: str,
        persona: str,
    ) -> List[Message]:
        """
        Construct the list of messages to send to the LLM.

        :param current_step: Current step.
        :param tools: Dictionary of tools.
        :param history: Conversation history.
        :param system_message: System prompt.
        :param persona: Agent persona.
        :return: List of Message objects.
        """
        messages = []
        system_prompt = system_message + "\n"
        system_prompt += f"{persona}\n\n"
        system_prompt += f"Instructions: {current_step.description.strip()}\n"
        system_prompt += (
            f"Available Routes:\n{self.get_routes_desc(current_step)}\n"
            if current_step.routes
            else ""
        )
        system_prompt += (
            f"\nAvailable Tools:\n{self.get_tools_desc(tools, current_step.tool_ids)}\n"
            if current_step.tool_ids
            else ""
        )
        messages.append(Message(role="system", content=system_prompt))
        user_prompt = f"History:\n{self.format_history(history)}"
        messages.append(Message(role="user", content=user_prompt))
        return messages

    def get_output(
        self,
        messages: List[Message],
        response_format: BaseModel,
        **kwargs: Any,  # noqa: ANN401
    ) -> BaseModel:
        """
        Get a structured response from the LLM.

        :param messages: List of Message objects.
        :param response_format: Pydantic model for the expected response.
        :param kwargs: Additional parameters for the LLM.
        :return: Parsed response as a BaseModel.
        """
        raise NotImplementedError("Subclasses should implement this method.")

    def _get_output(
        self,
        steps: Dict[str, Step],
        current_step: Step,
        tools: Dict[str, Tool],
        history: List[Union[Message, StepIdentifier, Summary]],
        response_format: BaseModel,
        system_message: Optional[str] = None,
        persona: Optional[str] = None,
        remote_tools: Optional[List[RemoteTool]] = None,
    ) -> BaseModel:
        """
        Get a structured response from the LLM using the agent's context.

        :param steps: Dictionary of all steps. (step_id -> Step)
        :param current_step: Current step.
        :param tools: Dictionary of tools.
        :param history: Conversation history.
        :param response_format: Pydantic model for the expected response.
        :param system_message: Optional system prompt.
        :param persona: Optional agent persona.
        :return: Parsed response as a BaseModel.
        """
        history = [
            steps[item.step_id] if isinstance(item, StepIdentifier) else item
            for item in history
        ]
        messages = self.get_messages(
            current_step=current_step,
            tools=tools,
            history=history,
            system_message=(
                system_message if system_message else DEFAULT_SYSTEM_MESSAGE.strip()
            ),
            persona=persona if persona else DEFAULT_PERSONA.strip(),
        )
        kwargs = {}
        if remote_tools:
            kwargs["remote_tools"] = remote_tools

        return self.get_output(
            messages=messages,
            response_format=response_format,
            **kwargs,
        )

    def generate(
        self,
        messages: List[Message],
        **kwargs: Any,  # noqa: ANN401
    ) -> str:
        """
        Generate a response from the LLM based on the provided messages.

        :param messages: List of Message objects.
        :param kwargs: Additional parameters for the LLM.
        :return: Generated response as a string.
        """
        raise NotImplementedError("Subclasses should implement this method.")

    def token_counter(self, text: str) -> int:
        """Count the number of tokens in a string."""
        return len(text.split())

    def format_remote_tools(self, remote_tools: List[RemoteTool]) -> list:
        """
        Format remote tools for passing to the LLM.

        :param remote_tools: List of RemoteTool objects.
        :return: list of formatted remote tools.
        """
        raise NotImplementedError("Subclasses should implement this method.")


__all__ = ["LLMBase"]
