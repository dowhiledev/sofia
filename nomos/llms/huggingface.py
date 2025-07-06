"""HuggingFace LLM integration for Nomos."""

from typing import List

from pydantic import BaseModel

from ..models.agent import Message
from .base import LLMBase


class HuggingFace(LLMBase):
    """HuggingFace Inference API integration."""

    __provider__: str = "huggingface"

    def __init__(self, model: str, **kwargs) -> None:
        """Initialize the HuggingFace inference client."""
        try:
            from huggingface_hub import InferenceClient
        except ImportError as exc:  # pragma: no cover - dependency check
            raise ImportError(
                "huggingface_hub package is not installed. Please install it using 'pip install nomos[huggingface]'."
            ) from exc

        self.model = model
        self.client = InferenceClient(**kwargs)

    def get_output(
        self,
        messages: List[Message],
        response_format: BaseModel,
        **kwargs: dict,
    ) -> BaseModel:
        """Get a structured response from HuggingFace."""
        _messages = [msg.model_dump() for msg in messages]
        comp = self.client.chat.completions.create(
            model=self.model,
            messages=_messages,
            response_format=response_format,
            **kwargs,
        )
        return comp.choices[0].message.parsed

    def generate(self, messages: List[Message], **kwargs: dict) -> str:
        """Generate a plain text response from HuggingFace."""
        _messages = [msg.model_dump() for msg in messages]
        comp = self.client.chat.completions.create(model=self.model, messages=_messages, **kwargs)
        return comp.choices[0].message.content if comp.choices else ""


__all__ = ["HuggingFace"]
