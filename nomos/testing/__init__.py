"""Unit Testing utilities for Nomos agents."""

from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel, Field

from nomos.llms import LLMBase
from nomos.models.agent import Message


class AssertionResult(BaseModel):
    """LLM structured output for expectation checks."""

    reasoning: List[str] = Field(..., description="Step by step reasoning")
    success: bool = Field(..., description="Whether expectation is met")
    assertion: Optional[str] = Field(None, description="Assertion message if failed")


def smart_assert(result: BaseModel, expectation: str, llm: LLMBase) -> None:
    """Check if the agent output meets the expectation using LLM.

    param result: The result from the agent.
    param expectation: The expectation to check against the result.
    param llm: The LLM instance to use for checking.
    Raises:
        AssertionError: If the expectation is not met.
    """
    messages = [
        Message(
            role="system",
            content=(
                "You evaluate if the agent output meets the expectation. "
                "Respond using the provided schema."
            ),
        ),
        Message(
            role="user",
            content=f"Expectation: {expectation}\nOutput: {result.model_dump_json()}",
        ),
    ]
    check = llm.get_output(messages=messages, response_format=AssertionResult)
    if not check.success:
        err_msg = (
            f"{check.assertion or 'Expectation not met'}\n"
            f"Expectation: {expectation}\n"
            f"Reasoning: {', '.join(check.reasoning)}"
        )
        raise AssertionError(err_msg)


__all__ = ["smart_assert", "AssertionResult"]
