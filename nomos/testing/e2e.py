"""Perform end-to-end testing of an agent with a scenario."""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import List, Optional, Tuple

from pydantic import BaseModel, Field

from ..core import Agent
from ..models.agent import Message, State


class SimulationDecision(Enum):  # noqa
    CONTINUE = "Continue the conversation"
    ASSERT = "Expectation are not met, assert with a reason"


class NextInput(BaseModel):  # noqa
    reasoning: List[str] = Field(..., description="Reason Step by step on deciding what to do next")
    decision: SimulationDecision = Field(
        ..., description="What to do next, either continue the conversation or assert"
    )
    input: Optional[str] = Field(
        None,
        description=(
            "The input that need to be given to the agent next,"
            " If decided to continue the conversation"
        ),
    )
    assertion: Optional[str] = Field(
        None,
        description="The assertion that need to be made if the decision is to assert",
    )


class Scenario(BaseModel):
    """Scenario to run against an agent."""

    scenario: str
    expectation: str


class ScenarioRunner:
    """Run a scenario against an agent and verify expectations."""

    @staticmethod
    def run(
        agent: Agent, scenario: Scenario, max_turns: int = 5
    ) -> Tuple[List[Message], List[Tuple[datetime, Optional[State]]]]:
        """
        Run a scenario against an agent and verify expectations.

        :param agent: The agent to run the scenario against.
        :param scenario: The scenario to run.
        :param max_turns: Maximum number of turns to run in the scenario.
        :return: List of tuples containing the timestamp and session data at each turn.
        """
        llm = agent.llm if not isinstance(agent.llm, dict) else agent.llm.get("global", None)
        assert llm, "LLM must be provided in the agent."
        session_data = None
        session_history: List[tuple[datetime, Optional[State]]] = []
        chat_history: List[Message] = []

        user_input = None
        turns = 0
        while True:
            res = agent.next(user_input, session_data)
            session_data = res.state
            chat_history.append(
                Message(
                    role="agent",
                    content=str(res.decision.response) if res.decision.response else "No response",
                )
            )
            session_history.append((datetime.now(), session_data))

            action = getattr(res.decision, "action", None)
            if getattr(action, "value", action) == "END":
                break
            if turns >= max_turns:
                raise AssertionError(
                    "Maximum number of turns reached without meeting expectations."
                )

            chat_history_str = "\n".join(str(msg) for msg in chat_history)
            next_input: NextInput = llm.get_output(
                messages=[
                    Message(
                        role="system",
                        content=(
                            "You are simulating a user interacting with an agent. "
                            "You are at the starting point or at a certain point in the conversation. "
                            "Do not rush the conversation, follow the scenario provided as your guide. "
                            "Decide the next input or assert if the expectation is not met until the current point. "
                        ),
                    ),
                    Message(
                        role="user",
                        content=(
                            f"Scenario: {scenario.scenario}\n"
                            f"Expectation: {scenario.expectation}\n"
                            f"Chat History:\n{chat_history_str}"
                        ),
                    ),
                ],
                response_format=NextInput,
            )

            if next_input.decision == SimulationDecision.ASSERT:
                err_msg = (
                    f"{next_input.assertion or 'Expectation are not met'}\n"
                    f"Reasoning: {'; '.join(next_input.reasoning)}\n"
                    f"Chat History:\n{chat_history_str}"
                )
                raise AssertionError(err_msg)

            user_input = next_input.input or ""
            chat_history.append(Message(role="you", content=user_input))
            turns += 1

        return chat_history, session_history


__all__ = ["ScenarioRunner", "Scenario", "SimulationDecision", "NextInput"]
