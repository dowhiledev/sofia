"""AgentConfig class for managing agent configurations."""

import os
from typing import Dict, List, Optional

from pydantic import BaseModel

from pydantic_settings import BaseSettings


from .llms import LLMBase, LLMConfig, OpenAI
from .memory import MemoryConfig
from .models.agent import Step
from .models.flow import FlowConfig
from .models.tool import MCPServer


class ServerConfig(BaseModel):
    """Configuration for the FastAPI server."""

    openai_api_key: Optional[str] = None
    redis_url: Optional[str] = None
    database_url: Optional[str] = None
    enable_tracing: bool = False
    port: int = 8000
    workers: int = 1


class AgentConfig(BaseSettings):
    """
    Configuration for the agent, including model settings and flow steps.

    Attributes:
        name (str): Name of the agent.
        persona (Optional[str]): Persona of the agent. Recommended to use a default persona.
        steps (List[Step]): List of steps in the flow.
        start_step_id (str): ID of the starting step.
        tool_arg_descriptions (Dict[str, Dict[str, str]]): Descriptions for tool arguments.
        system_message (Optional[str]): System message for the agent. Default system message will be used if not provided.
        show_steps_desc (bool): Flag to show step descriptions.
        max_errors (int): Maximum number of errors allowed.
        max_iter (int): Maximum number of iterations allowed.
        llm (Optional[LLMConfig]): Optional LLM configuration.
    Methods:
        from_yaml(file_path: str) -> "AgentConfig": Load configuration from a YAML file.
        to_yaml(file_path: str) -> None: Save configuration to a YAML file.
    """

    name: str
    persona: Optional[str] = None  # Recommended to use a default persona
    steps: List[Step]
    start_step_id: str
    tool_arg_descriptions: Optional[Dict[str, Dict[str, str]]] = None
    system_message: Optional[str] = (
        None  # Default system message will be used if not provided
    )
    show_steps_desc: bool = False
    max_errors: int = 3
    max_iter: int = 10

    llm: Optional[LLMConfig] = None  # Optional LLM configuration

    memory: Optional[MemoryConfig] = None  # Optional memory configuration

    flows: Optional[List[FlowConfig]] = None  # Optional flow configurations

    server: ServerConfig = ServerConfig()

    mcp_servers: Optional[List[MCPServer]] = None  # Optional MCP server configurations

    @classmethod
    def from_yaml(cls, file_path: str) -> "AgentConfig":
        """
        Load configuration from a YAML file.

        :param file_path: Path to the YAML file.
        :return: An instance of AgentConfig with the loaded data.
        """
        import yaml

        with open(file_path, "r") as file:
            data = yaml.safe_load(file)
        server_data = data.get("server", {})
        if isinstance(server_data, dict):
            expanded = {
                k: (
                    os.getenv(v[1:], v)
                    if isinstance(v, str) and v.startswith("$")
                    else v
                )
                for k, v in server_data.items()
            }
            data["server"] = expanded
        return cls(**data)

    def to_yaml(self, file_path: str) -> None:
        """
        Save configuration to a YAML file.

        :param file_path: Path to the YAML file.
        """
        import yaml

        with open(file_path, "w") as file:
            yaml.dump(self.model_dump(), file)

    def get_llm(self) -> LLMBase:
        """
        Get the appropriate LLM instance based on the configuration.

        :return: An instance of the defined LLM integration.
        """
        return self.llm.get_llm() if self.llm else OpenAI()


__all__ = ["AgentConfig", "ServerConfig"]
