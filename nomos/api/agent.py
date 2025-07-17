"""Nomos Agent Initialization."""

import os

# Initialize Tracing
if os.getenv("ENABLE_TRACING", "false").lower() == "true":
    from opentelemetry.sdk.resources import Resource

    from nomos.utils.tracing import initialize_tracing

    initialize_tracing(
        tracer_provider_kwargs={
            "resource": Resource(
                {
                    "service.name": os.getenv("SERVICE_NAME", "nomos-agent"),
                    "service.version": os.getenv("SERVICE_VERSION", "0.0.1"),
                }
            )
        }
    )

import nomos  # noqa
from nomos.llms.openai import OpenAI

from .tools import tool_list

config = nomos.AgentConfig.from_yaml(os.getenv("CONFIG_PATH", "config.agent.yaml"))
llm = config.get_llm() if hasattr(config, "llm") and config.llm else OpenAI()
agent = nomos.Agent.from_config(config, llm, tool_list)

__all__ = ["agent", "config"]
