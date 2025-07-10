from typing import List

from pydantic import BaseModel

from ..models.agent import Message
from .base import LLMBase


class Groq(LLMBase):
    """Groq LLM integration for Nomos."""

    __provider__: str = "groq"

    def __init__(self, model: str = "llama3-8b-8192", **kwargs) -> None:
        """
        Initialize the Groq LLM.

        :param model: Model name to use (default: llama3-8b-8192).
        :param kwargs: Additional parameters for Groq API.
        """
        try:
            import instructor
            from groq import Groq
        except ImportError:
            raise ImportError(
                "Groq package is not installed. Please install it using 'pip install nomos[groq]."
            )

        self.model = model
        kwargs.pop("embedding_model", None)
        client = Groq(**kwargs)
        self.client = instructor.from_groq(client, mode=instructor.Mode.JSON)

    def get_output(
        self,
        messages: List[Message],
        response_format: BaseModel,
        **kwargs: dict,
    ) -> BaseModel:
        """Get a structured response from the Groq LLM.
        :param messages: List of Message objects.
        :param response_format: Pydantic model for the expected response.
        :param kwargs: Additional parameters for Groq API.
        :return: Parsed response as a BaseModel.
        """

        _messages = [msg.model_dump() for msg in messages]
        completion = self.client.chat.completions.create(
            messages=_messages,
            model=self.model,
            response_model=response_format,
            **kwargs,
        )

        return completion
