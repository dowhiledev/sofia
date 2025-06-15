"""Tests for the financial advisor agent."""

import os
import pytest

from nomos import Agent, AgentConfig


@pytest.fixture
def financial_advisor_agent() -> Agent:
    """Fixture to create a financial advisor agent."""
    from tools import tools

    config = AgentConfig.from_yaml(
        os.path.join(
            os.path.dirname(__file__),
            "config.agent.yaml",
        )
    )
    agent = Agent.from_config(config, tools=tools)
    return agent
