"""AgentConfig class for managing agent configurations."""

import importlib
import importlib.util
import os
from typing import Callable, Dict, List, Optional, Union

from pydantic import BaseModel
from pydantic_settings import BaseSettings

from .config.session_config import SessionConfig
from .llms import LLMBase, LLMConfig, OpenAI
from .memory import MemoryConfig
from .models.agent import Step
from .models.flow import FlowConfig
from .models.tool import ToolDef, ToolWrapper
from .utils.utils import convert_camelcase_to_snakecase


class ServerConfig(BaseModel):
    """Configuration for the FastAPI server."""

    redis_url: Optional[str] = None
    database_url: Optional[str] = None
    enable_tracing: bool = False
    port: int = 8000
    workers: int = 1


class ExternalTool(BaseModel):
    """Configuration for an external tool."""

    tag: str  # Tag of the external tool (eg - @pkg/itertools.combinations, @crewai/FileReadTool, @langchain/BingSearchAPIWrapper)
    name: Optional[str] = (
        None  # snake case name of the tool (eg - combinations, file_read_tool, bing_search)
    )
    kwargs: Optional[Dict[str, Union[str, int, float]]] = (
        None  # Optional keyword arguments for the Tool initialization
    )

    def get_tool_wrapper(self) -> ToolWrapper:
        """
        Get the ToolWrapper instance for the external tool.

        :return: ToolWrapper instance.
        """
        tool_type, tool_name = self.tag.split("/", 1)
        tool_type = tool_type.replace("@", "")
        if tool_type == "mcp" and not self.name:
            raise ValueError("For MCP tools, the 'name' field is required.")

        name = self.name or convert_camelcase_to_snakecase(tool_name.split(".")[-1])
        assert tool_type in [
            "pkg",
            "crewai",
            "langchain",
            "mcp",
        ], (
            f"Unsupported tool type: {tool_type}. Supported types are 'pkg', 'crewai', 'mcp' and 'langchain'."
        )
        return ToolWrapper(
            name=name,
            tool_type=tool_type,
            tool_identifier=tool_name,
            kwargs=self.kwargs,
        )


class ToolsConfig(BaseModel):
    """Configuration for tools used by the agent."""

    tool_files: List[str] = []  # List of tool files to load
    external_tools: Optional[List[ExternalTool]] = None  # List of external tools
    tool_defs: Optional[Dict[str, ToolDef]] = None

    def get_tools(self) -> List[Union[Callable, ToolWrapper]]:
        """
        Load and return the tools based on the configuration.

        :return: List of tool functions.
        """
        tools_list: List = []
        # Load Tools for python files
        for tool_file in self.tool_files:
            try:
                # Handle both file paths and module names
                if tool_file.endswith(".py"):
                    # It's a file path
                    if not os.path.exists(tool_file):
                        raise FileNotFoundError(f"Tool file '{tool_file}' does not exist.")

                    # Load module from file path
                    spec = importlib.util.spec_from_file_location("tool_module", tool_file)
                    if spec is None or spec.loader is None:
                        raise ImportError(f"Could not load module from '{tool_file}'")
                    module = importlib.util.module_from_spec(spec)
                    spec.loader.exec_module(module)
                else:
                    # It's a module name, try to import it directly
                    module = importlib.import_module(tool_file)

                # Extract tools from the module
                tools = module.tools if hasattr(module, "tools") else []
                tools_list.extend(tools)

            except (ImportError, FileNotFoundError, AttributeError) as e:
                raise ImportError(f"Failed to load tools from '{tool_file}': {e}")

        # Load external tools
        for external_tool in self.external_tools or []:
            try:
                tool_wrapper = external_tool.get_tool_wrapper()
                tools_list.append(tool_wrapper)
            except ValueError as e:
                raise ValueError(f"Failed to load external tool '{external_tool.tag}': {e}")

        return tools_list


class LoggingHandler(BaseModel):
    """Configuration for a logging handler."""

    type: str  # Type of the logging handler (e.g., 'stderr', 'file')
    level: str
    format: str = "{time:YYYY-MM-DD at HH:mm:ss} | {level} | {message}"


class LoggingConfig(BaseModel):
    """Configuration for logging."""

    enable: bool
    handlers: List[LoggingHandler] = []


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
        max_examples (int): Maximum number of examples to use in decision-making.
        threshold (float): Minimum similarity score to include an example.
        max_iter (int): Maximum number of iterations allowed.
        llm (Optional[LLMConfig]): Optional LLM configuration.
        embedding_model (Optional[LLMConfig]): Optional embedding model configuration.
        memory (Optional[MemoryConfig]): Optional memory configuration.
        flows (Optional[List[FlowConfig]]): Optional flow configurations.
        server (ServerConfig): Configuration for the FastAPI server.
        tools (ToolsConfig): Configuration for tools.
        logging (Optional[LoggingConfig]): Optional logging configuration.
    Methods:
        from_yaml(file_path: str) -> "AgentConfig": Load configuration from a YAML file.
        to_yaml(file_path: str) -> None: Save configuration to a YAML file.
    """

    name: str
    persona: Optional[str] = None  # Recommended to use a default persona
    steps: List[Step]
    start_step_id: str
    system_message: Optional[str] = None  # Default system message will be used if not provided
    show_steps_desc: bool = False
    max_errors: int = 3
    max_iter: int = 10
    max_examples: int = 5  # Maximum number of examples to use in decision-making
    threshold: float = 0.5  # Minimum similarity score to include an example

    llm: Optional[LLMConfig] = None  # Optional LLM configuration
    embedding_model: Optional[LLMConfig] = None  # Optional embedding model configuration
    memory: Optional[MemoryConfig] = None  # Optional memory configuration
    flows: Optional[List[FlowConfig]] = None  # Optional flow configurations

    server: ServerConfig = ServerConfig()  # Configuration for the FastAPI server
    tools: ToolsConfig = ToolsConfig()  # Configuration for tools

    # Optional session store configuration
    session: Optional[SessionConfig] = None

    logging: Optional[LoggingConfig] = None  # Optional logging configuration

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
                k: (os.getenv(v[1:], v) if isinstance(v, str) and v.startswith("$") else v)
                for k, v in server_data.items()
            }
            data["server"] = expanded

        session_data = data.get("session") or data.get("session_store")
        if isinstance(session_data, dict):
            expanded = {
                k: (os.getenv(v[1:], v) if isinstance(v, str) and v.startswith("$") else v)
                for k, v in session_data.items()
            }
            data["session"] = expanded

        return cls(**data)

    def to_yaml(self, file_path: str) -> None:
        """
        Save configuration to a YAML file.

        :param file_path: Path to the YAML file.
        """
        import yaml

        with open(file_path, "w") as file:
            yaml.dump(self.model_dump(mode="json"), file, sort_keys=False)

    def get_llm(self) -> LLMBase:
        """
        Get the appropriate LLM instance based on the configuration.

        :return: An instance of the defined LLM integration.
        """
        return self.llm.get_llm() if self.llm else OpenAI()

    def get_embedding_model(self) -> Optional[LLMBase]:
        """
        Get the appropriate embedding model instance based on the configuration.

        :return: An instance of the defined embedding model integration.
        """
        return self.embedding_model.get_llm() if self.embedding_model else None


__all__ = ["AgentConfig", "ServerConfig", "SessionConfig"]
