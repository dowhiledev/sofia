"""OpenAI LLM integration for Nomos."""

import json
from typing import List, Optional

from pydantic import BaseModel

from ..models.agent import Message
from .base import LLMBase


class Cohere(LLMBase):
    """OpenAI Chat LLM integration for Nomos."""

    __provider__: str = "cohere"

    def __init__(
        self,
        model: str = "command-a-03-2025",
        embedding_model: Optional[str] = None,
        **kwargs,
    ) -> None:
        """
        Initialize the CohereLLM.

        :param model: Model name to use (default: command-a-03-2025).
        :param embedding_model: Model name for embeddings (default: embed-v4.0).
        :param kwargs: Additional parameters for OpenAI API.
        """
        try:
            from cohere import ClientV2
        except ImportError:
            raise ImportError(
                "OpenAI package is not installed. Please install it using 'pip install nomos[openai]."
            )

        self.model = model
        self.embedding_model = embedding_model or "embed-v4.0"
        self.client = ClientV2(**kwargs)

    def get_output(
        self,
        messages: List[Message],
        response_format: BaseModel,
        **kwargs: dict,
    ) -> BaseModel:
        """
        Get a structured response from the OpenAI LLM.

        :param messages: List of Message objects.
        :param response_format: Pydantic model for the expected response.
        :param kwargs: Additional parameters for OpenAI API.
        :return: Parsed response as a BaseModel.
        """
        _messages = [msg.model_dump() for msg in messages]
        comp = self.client.chat(
            model=self.model,
            messages=_messages,
            response_format={"type": "json_object", "schema": response_format.model_json_schema()},
            **kwargs,
        )
        return response_format.model_validate(json.loads(comp.message.content[0].text))

    def generate(
        self,
        messages: List[Message],
        **kwargs: dict,
    ) -> str:
        """
        Generate a response from the Cohere LLM based on the provided messages.

        :param messages: List of Message objects.
        :param kwargs: Additional parameters for OpenAI API.
        :return: Generated response as a string.
        """
        _messages = [msg.model_dump() for msg in messages]
        comp = self.client.chat(
            model=self.model,
            messages=_messages,
            **kwargs,
        )
        return comp.message.content[0].text

    def token_counter(self, text: str) -> int:
        """Count tokens using tiktoken for the current model."""
        return len(
            self.client.tokenize(
                text=text,
                model=self.model,
            ).tokens
        )

    def embed_text(self, text: str) -> List[float]:
        """Embed a single text using the OpenAI embeddings API."""
        response = self.client.embed(
            model=self.embedding_model,
            texts=[text],
            input_type="search_document",
            output_dimension=1024,
            embedding_types=["float"],
        )
        embs = response.embeddings.float_
        assert embs is not None, "Embedding response is None"
        return embs[0]

    def embed_batch(self, texts: List[str]) -> List[List[float]]:
        """Embed a batch of texts using the OpenAI embeddings API."""
        response = self.client.embed(
            model=self.embedding_model,
            texts=texts,
            input_type="search_document",
            output_dimension=1024,
            embedding_types=["float"],
        )
        embs = response.embeddings.float_
        assert embs is not None
        return embs


__all__ = ["Cohere"]
