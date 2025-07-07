"""Tests for :class:`AgentGenerator`."""

from unittest.mock import patch

from nomos.utils.generator import (
    AgentConfiguration,
    AgentGenerator,
    Route,
    Step,
)


def test_agent_generator_generate(monkeypatch, mock_llm):
    """Verify basic flow of ``AgentGenerator.generate``."""

    mock_llm.set_generate_response("initial plan")

    # Monkeypatch confirmation to stop after first plan
    monkeypatch.setattr("nomos.utils.generator.Confirm.ask", lambda *_args, **_kw: True)

    # Use dummy LLM by replacing the generator's LLM after init
    with patch("nomos.utils.generator.LLMConfig.get_llm", return_value=mock_llm):
        generator = AgentGenerator()

    # Prepare structured response returned by get_output
    config = AgentConfiguration(
        name="demo",
        persona="p",
        steps=[Step(step_id="s", description="d", routes=[Route(target="s", condition="c")])],
        start_step_id="s",
    )
    mock_llm.set_response(config)

    result = generator.generate("use")

    assert isinstance(result, AgentConfiguration)
    assert result.name == "demo"
    # Ensure the LLM received messages for both generate and get_output
    assert len(mock_llm.messages_received) > 0
