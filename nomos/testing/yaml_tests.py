"""Utilities to load agent tests from YAML configuration."""

from __future__ import annotations

from pathlib import Path
from typing import Dict, List, Optional, Union

import yaml
from pydantic import BaseModel, Field

from nomos.llms import LLMConfig
from nomos.models.agent import Message, State, StepIdentifier, Summary


class HistoryItem(BaseModel):
    """Item representing a piece of conversation history."""

    type: str = Field(..., description="Type of history item")
    summary: Optional[List[str]] = None
    role: Optional[str] = None
    content: Optional[str] = None
    step_id: Optional[str] = None

    def to_obj(self) -> Union[Summary, Message, StepIdentifier]:
        """Convert to Nomos history object."""
        if self.type == "summary":
            return Summary(summary=self.summary or [])
        if self.type == "message":
            return Message(role=self.role or "user", content=self.content or "")
        if self.type == "step_identifier":
            return StepIdentifier(step_id=self.step_id or "")
        raise ValueError(f"Unsupported history item type: {self.type}")


class UnitTestCase(BaseModel):
    """Definition of a unit test case."""

    context: Optional[dict] = None
    input: str
    verbose: bool = False
    expectation: str
    invalid: bool = False

    def build_context(self) -> Optional[State]:
        """Build a session ``State`` from the provided context data."""
        if not self.context:
            return None
        history = self.context.get("history") or []
        current_step_id = self.context.get("current_step_id")
        ctx = State(
            current_step_id=current_step_id, history=[HistoryItem(**h).to_obj() for h in history]
        )
        return ctx


class E2ETestCase(BaseModel):
    """Definition of an end-to-end scenario test."""

    scenario: str
    expectation: str
    max_steps: int = 10


class TestSuite(BaseModel):
    """Container for YAML defined tests."""

    llm: Optional[LLMConfig] = None
    unit: Dict[str, UnitTestCase] = Field(default_factory=dict)
    e2e: Dict[str, E2ETestCase] = Field(default_factory=dict)


def load_yaml_tests(path: Union[str, Path]) -> TestSuite:
    """Load a TestSuite from YAML file."""
    with open(path, "r") as f:
        data = yaml.safe_load(f)
    return TestSuite(**(data or {}))


__all__ = ["TestSuite", "UnitTestCase", "E2ETestCase", "HistoryItem", "load_yaml_tests"]
