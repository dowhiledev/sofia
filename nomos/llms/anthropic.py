"""Anthropic LLMs integration for Nomos."""

from typing import List

from pydantic import BaseModel

from ..models.agent import Message
from .base import LLMBase


class Anthropic(LLMBase):
    """Anthropic Chat LLM integration for Nomos."""

    __provider__: str = "anthropic"

    def __init__(self, model: str = "claude-sonnet-4-20250514", **kwargs) -> None:
        """
        Initialize the Anthropic LLM.

        :param model: Model name to use (default: claude-3-5-sonnet-20241022).
        :param kwargs: Additional parameters for Anthropic API.
        """
        try:
            from anthropic import Anthropic as AnthropicClient
        except ImportError:
            raise ImportError(
                "Anthropic package is not installed. Please install it using 'pip install nomos[anthropic]'."
            )

        self.model = model
        self.client = AnthropicClient(**kwargs)

    def get_output(
        self,
        messages: List[Message],
        response_format: BaseModel,
        **kwargs: dict,
    ) -> BaseModel:
        """
        Get a structured response from the Anthropic LLM.

        :param messages: List of Message objects.
        :param response_format: Pydantic model for the expected response.
        :param kwargs: Additional parameters for Anthropic API.
        :return: Parsed response as a BaseModel.
        """
        from anthropic.types import Message as AnthropicMessage

        # Convert messages to Anthropic format
        _messages = []
        system_message = None

        for msg in messages:
            if msg.role == "system":
                system_message = msg.content
            else:
                _messages.append({"role": msg.role, "content": msg.content})

        # Create a tool for structured output
        _output_tool = {
            "name": kwargs.get("output_tool_name", "get_next_decision"),
            "description": kwargs.get(
                "output_tool_description", "Get the next decision based on the input."
            ),
            "input_schema": response_format.model_json_schema(),
        }

        response: AnthropicMessage = self.client.messages.create(
            model=self.model,
            tools=[_output_tool],
            system=system_message or "",
            messages=_messages,
            **kwargs,
        )
        tool_use = next(block for block in response.content if block.type == "tool_use")
        assert tool_use.name == _output_tool["name"], "Unexpected tool use name in response"
        assert tool_use.input, "Tool use input is empty"
        return response_format.model_validate(tool_use.input)

    def generate(
        self,
        messages: List[Message],
        **kwargs: dict,
    ) -> str:
        """
        Generate a plain text response from the Anthropic LLM.

        :param messages: List of Message objects.
        :param kwargs: Additional parameters for Anthropic API.
        :return: Generated text response.
        """
        from anthropic.types import Message as AnthropicMessage

        # Convert messages to Anthropic format
        _messages = []
        system_message = None

        for msg in messages:
            if msg.role == "system":
                system_message = msg.content
            else:
                _messages.append({"role": msg.role, "content": msg.content})

        # Make the API call
        response: AnthropicMessage = self.client.messages.create(
            model=self.model, system=system_message or "", messages=_messages, **kwargs
        )

        text = next(
            (block.content for block in response.content if block.type == "text"),
            None,
        )
        if text is None:
            raise ValueError("No text content found in the response.")
        return text

    def token_counter(self, text: str) -> int:
        """Count the number of tokens in the given text."""
        return super().token_counter(text)


__all__ = ["Anthropic"]
