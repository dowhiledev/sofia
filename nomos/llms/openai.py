"""OpenAI LLM integration for SOFIA."""

from typing import Any, List

from pydantic import BaseModel

from .base import LLMBase
from ..models.agent import Message
from ..models.tool import RemoteTool
from ..utils.url import join_urls


class OpenAI(LLMBase):
    """OpenAI Chat LLM integration for SOFIA."""

    __provider__: str = "openai"

    def __init__(self, model: str = "gpt-4o-mini", **kwargs) -> None:
        """
        Initialize the OpenAIChatLLM.

        :param model: Model name to use (default: gpt-4o-mini).
        :param kwargs: Additional parameters for OpenAI API.
        """
        try:
            from openai import OpenAI
        except ImportError:
            raise ImportError(
                "OpenAI package is not installed. Please install it using 'pip install nomos[openai]."
            )

        self.model = model
        self.client = OpenAI(**kwargs)

    def get_output(
        self,
        messages: List[Message],
        response_format: BaseModel,
        **kwargs: Any,  # noqa: ANN401
    ) -> BaseModel:
        """
        Get a structured response from the OpenAI LLM.

        :param messages: List of Message objects.
        :param response_format: Pydantic model for the expected response.
        :param kwargs: Additional parameters for OpenAI API.
        :return: Parsed response as a BaseModel.
        """
        _messages = [msg.model_dump() for msg in messages]
        remote_tools = kwargs.pop("remote_tools", None)
        if remote_tools:
            # Format remote tools for OpenAI API
            formatted_tools = self.format_remote_tools(remote_tools)
            kwargs["tools"] = formatted_tools

        comp = self.client.responses.parse(
            model=self.model,
            input=_messages,
            text_format=response_format,
            **kwargs,
        )
        return comp.output_parsed

    def generate(
        self,
        messages: List[Message],
        **kwargs: Any,  # noqa: ANN401
    ) -> str:
        """
        Generate a response from the OpenAI LLM based on the provided messages.

        :param messages: List of Message objects.
        :param kwargs: Additional parameters for OpenAI API.
        :return: Generated response as a string.
        """
        from openai.types.chat import ChatCompletion

        _messages = [msg.model_dump() for msg in messages]
        comp: ChatCompletion = self.client.chat.completions.create(
            messages=_messages,
            model=self.model,
            **kwargs,
        )
        return comp.choices[0].message.content if comp.choices else ""  # type: ignore

    def token_counter(self, text: str) -> int:
        """Count tokens using tiktoken for the current model."""
        import tiktoken

        enc = tiktoken.encoding_for_model(self.model)
        return len(enc.encode(text))

    def format_remote_tools(self, remote_tools: List[RemoteTool]) -> List[dict]:
        """
        Format remote tools for OpenAI API.

        :param remote_tools: List of RemoteTool objects.
        :return: List of formatted tool dictionaries.
        """
        server_name_to_config: dict[str, dict] = {}
        for tool in remote_tools:
            if tool.type != RemoteTool.RemoteToolType.mcp.value:
                continue

            server_name = tool.server.name
            if server_name in server_name_to_config:
                server_config = server_name_to_config[server_name]
                server_config["allowed_tools"].append(tool.name)
            else:
                server_url = join_urls(str(tool.server.url), tool.server.path)
                server_config = {
                    "type": "mcp",
                    "server_label": server_name,
                    "server_url": server_url,
                    "require_approval": "never",
                    "allowed_tools": [tool.name],
                }
            server_name_to_config[server_name] = server_config

        return list(server_name_to_config.values())


__all__ = ["OpenAI"]
