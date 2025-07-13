"""Gemini LLM integration for Nomos."""

from typing import List

from pydantic import BaseModel

from ..models.agent import Message
from .base import LLMBase


class Gemini(LLMBase):
    """Gemini LLM integration for Nomos."""

    __provider__: str = "google"

    def __init__(self, model: str = "gemini-2.0-flash", **kwargs) -> None:
        """
        Initialize the Gemini LLM.

        :param model: Model name to use (default: gemini-2.0-flash).
        :param kwargs: Additional parameters for Gemini API.
        """
        from google.genai import Client

        kwargs.pop("embedding_model", None)
        self.model = model
        self.client = Client(**kwargs)

    def get_output(
        self,
        messages: List[Message],
        response_format: BaseModel,
        **kwargs: dict,
    ) -> BaseModel:
        """
        Get a structured response from the Gemini LLM.

        :param messages: List of Message objects.
        :param response_format: Pydantic model for the expected response.
        :param kwargs: Additional parameters for Gemini API.
        :return: Parsed response as a BaseModel.
        """
        try:
            from google.genai import types
        except ImportError:
            raise ImportError(
                "Google GenAI package is not installed. Please install it using 'pip install nomos[google]."
            )

        system_message = next(msg.content for msg in messages if msg.role == "system")
        user_message = next(msg.content for msg in messages if msg.role == "user")

        comp = self.client.models.generate_content(
            model=self.model,
            contents=[user_message],
            config=types.GenerateContentConfig(
                system_instruction=system_message,
                response_mime_type="application/json",
                response_schema=response_format,
                **kwargs,
            ),
        )
        return comp.parsed


__all__ = ["Gemini"]
