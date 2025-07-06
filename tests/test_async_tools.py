import asyncio
import time

from nomos.config import AgentConfig, ToolsConfig
from nomos.core import Agent
from nomos.models.agent import Action, Route, Step
from nomos.models.tool import Tool


async def async_tool(arg0: str = "test") -> str:
    """Dummy asynchronous tool."""
    await asyncio.sleep(0.01)
    return f"async {arg0}"


async_tool.__name__ = "async_tool"


def test_async_tool_execution(mock_llm):
    steps = [
        Step(
            step_id="start",
            description="Start",
            routes=[Route(target="end", condition="done")],
            available_tools=["async_tool"],
        ),
        Step(step_id="end", description="End", routes=[], available_tools=[]),
    ]
    config = AgentConfig(
        name="async_agent",
        steps=steps,
        start_step_id="start",
        tools=ToolsConfig(),
    )
    agent = Agent.from_config(config=config, llm=mock_llm, tools=[async_tool])

    session = agent.create_session()

    tool_model = agent.llm._create_decision_model(
        current_step=session.current_step,
        current_step_tools=(Tool.from_function(async_tool),),
    )
    response = tool_model(
        reasoning=["do async"],
        action=Action.TOOL_CALL.value,
        tool_call={"tool_name": "async_tool", "tool_kwargs": {"arg0": "value"}},
    )
    session.llm.set_response(response)

    start = time.monotonic()
    res = session.next("run", return_tool=True)
    duration = time.monotonic() - start

    assert res.decision.action == Action.TOOL_CALL
    assert res.tool_output == "async value"
    assert duration < 0.5
