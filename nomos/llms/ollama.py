"""Ollama LLM integration for Nomos."""

from typing import List

from pydantic import BaseModel

from ..models.agent import Message
from .base import LLMBase


class Ollama(LLMBase):
    """Ollama LLM integration for Nomos."""

    __provider__: str = "ollama"

    def __init__(self, model: str = "llama3", **kwargs) -> None:
        """Initialize the Ollama LLM."""
        try:
            from ollama import Client
        except ImportError as exc:  # pragma: no cover - dependency check
            raise ImportError(
                "Ollama package is not installed. Please install it using 'pip install nomos[ollama]'."
            ) from exc

        self.model = model
        self.client = Client(**kwargs)

    def get_output(
        self,
        messages: List[Message],
        response_format: BaseModel,
        **kwargs: dict,
    ) -> BaseModel:
        """Get a structured response from Ollama."""
        _messages = [msg.model_dump() for msg in messages]
        resp = self.client.chat(
            model=self.model,
            messages=_messages,
            format=response_format.model_json_schema(),
            **kwargs,
        )
        content = resp["message"]["content"]
        return response_format.model_validate_json(content)

    def generate(self, messages: List[Message], **kwargs: dict) -> str:
        """Generate a plain text response from Ollama."""
        _messages = [msg.model_dump() for msg in messages]
        resp = self.client.chat(model=self.model, messages=_messages, **kwargs)
        return resp["message"]["content"] if resp else ""


__all__ = ["Ollama"]
