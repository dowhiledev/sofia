"""Tool abstractions and related logic for the Nomos package."""

import inspect
from enum import Enum
from typing import Any, Callable, Dict, Optional, Type


from docstring_parser import parse

from pydantic import BaseModel, HttpUrl, SecretStr, ValidationError

from ..utils.utils import create_base_model


def is_remote_tool(tool_name: str) -> bool:
    """
    Check if a tool name is an Remote tool.

    :param tool_name: The name of the tool.
    :return: True if it is an Remote tool, False otherwise.
    """
    if "mcp:" in tool_name:
        return True

    return False


def is_package_tool(tool_name: str) -> bool:
    """
    Check if a tool name is a package tool.

    :param tool_name: The name of the tool.
    :return: True if it is a package tool, False otherwise.
    """
    return ":" in tool_name and not is_remote_tool(tool_name)


class Tool(BaseModel):
    """
    Represents a tool that can be used in the agent's flow.

    Attributes:
        name (str): The name of the tool.
        description (str): A brief description of the tool.
        function (Callable): The function to be executed when the tool is called.
        parameters (Dict[str, Dict[str, Any]]): A dictionary of parameters for the function.
    Methods:
        from_function(function: Callable, tool_arg_descs: Dict[str, Dict[str, str]]) -> Tool:
            Create a Tool instance from a function and its argument descriptions.
        from_pkg(identifier: str, tool_arg_descs: Dict[str, Dict[str, str]]) -> Tool:
            Create a Tool instance from a package identifier.
        get_args_model() -> Type[BaseModel]:
            Get the Pydantic model for the tool's arguments.
        run(**kwargs) -> str:
            Execute the tool with the provided arguments.
    """

    name: str
    description: str
    function: Callable
    parameters: Dict[str, Dict[str, Any]] = {}
    _cached_args_model: Optional[Type[BaseModel]] = None

    @classmethod
    def from_function(
        cls,
        function: Callable,
        tool_arg_descs: Optional[Dict[str, Dict[str, str]]] = None,
    ) -> "Tool":
        """
        Create a Tool instance from a function and its argument descriptions.

        :param function: The function to be executed when the tool is called.
        :param tool_arg_descs: A dictionary of argument descriptions for the function.
        :return: An instance of Tool.
        """
        sig = inspect.signature(function)
        description = (
            parse(function.__doc__.strip()).short_description
            if function.__doc__
            else None
        )
        description = description or ""

        tool_arg_desc_doc_params = (
            parse(function.__doc__.strip()).params if function.__doc__ else []
        )
        tool_arg_desc_doc = {
            param.arg_name: param.description
            for param in tool_arg_desc_doc_params
            if param.description
        }
        if tool_arg_descs is None:
            tool_arg_descs = {}
        tool_arg_desc = tool_arg_descs.get(function.__name__, {})
        tool_arg_desc_doc.update(tool_arg_desc)
        tool_arg_desc = tool_arg_desc_doc.copy()

        params = {}
        for name, param in sig.parameters.items():
            param_info = {
                "type": (
                    param.annotation
                    if param.annotation is not inspect.Parameter.empty
                    else Any
                )
            }
            if tool_arg_desc.get(name):
                param_info["description"] = tool_arg_desc[name]
            if param.default is not inspect.Parameter.empty:
                param_info["default"] = param.default
            params[name] = param_info

        return cls(
            name=function.__name__,
            description=description,
            function=function,
            parameters=params,
        )

    @classmethod
    def from_pkg(
        cls, identifier: str, tool_arg_descs: Optional[Dict[str, Dict[str, str]]] = None
    ) -> "Tool":
        """
        Create a Tool instance from a package identifier.

        :param identifier: The package identifier in the format "library_name:tool_name".
        """
        library_name, tool_name = identifier.split(":")
        try:
            module = __import__(library_name)
            if tool_arg_descs is None:
                tool_arg_descs = {}
            _tool_arg_descs = getattr(module, "tool_arg_descs", tool_arg_descs)
            for submodule in tool_name.split("."):
                module = getattr(module, submodule)
            assert callable(module), f"{module} is not callable"
            return cls.from_function(module, _tool_arg_descs)
        except Exception as e:
            raise ValueError(f"Could not load tool {identifier}: {e}")

    def get_args_model(self) -> Type[BaseModel]:
        """
        Get the Pydantic model for the tool's arguments.

        :return: A Pydantic model representing the tool's arguments.
        """
        if self._cached_args_model:
            return self._cached_args_model
        camel_case_fn_name = self.name.replace("_", " ").title().replace(" ", "")
        basemodel_name = f"{camel_case_fn_name}Args"
        args_model = create_base_model(
            basemodel_name,
            self.parameters,
        )
        self._cached_args_model = args_model
        return args_model

    def run(self, *args, **kwargs) -> str:
        """
        Execute the tool with the provided arguments.

        :param kwargs: The arguments to be passed to the tool's function.
        :return: The result of the tool's function.
        """
        # Validate the arguments
        args_model = self.get_args_model()
        try:
            args_model(**kwargs)
        except ValidationError as e:
            raise InvalidArgumentsError(e)
        return str(self.function(*args, **kwargs))

    def __str__(self) -> str:
        """String representation of the Tool instance."""
        return f"Tool(name={self.name}, description={self.description})"


class FallbackError(Exception):
    """
    Fallback Instruction if a tool fails.

    So the agent can continue the flow.
    """

    def __init__(self, error: str, fallback: str) -> None:
        """
        Agent fallback exception.

        :param error: The error message.
        :param fallback: The fallback instruction.
        """
        super().__init__(error)
        self.error = error
        self.fallback = fallback

    def __str__(self) -> str:
        """Create a simplified validation error."""
        return f"Ran into an error: {self.error}. Follow this fallback instruction: {self.fallback}"


class InvalidArgumentsError(Exception):
    """Exception raised when an invalid argument is passed to a tool."""

    def __init__(self, error: ValidationError) -> None:
        """
        Invalid argument exception.

        :param error: The error message.
        """
        super().__init__(str(error))
        self.error = error

    def __str__(self) -> str:
        """Create a simplified validation error."""
        errors = self.error.errors()
        error_messages = []
        for error in errors:
            msg = error.get("msg")
            error_messages.append(msg) if msg else None
        return f"Invalid arguments: {', '.join(error_messages)}. Please Try again with valid arguments."


class MCPToolError(Exception):
    """Exception raised when there's an error with MCP tool execution."""

    def __init__(self, message: str, tool_name: str) -> None:
        """Initialize with error message and tool name."""
        self.message = message
        self.tool_name = tool_name
        super().__init__(f"Error with MCP tool '{tool_name}': {message}")


class MCPServer(BaseModel):
    """
    Represents a Model Configuration Protocol (MCP) server that provides tools.

    MCP servers expose tools that can be discovered and used by Nomos agents.
    Each tool on the server is made available as a Tool object in Nomos.

    Attributes:
        url (HttpUrl): The base URL of the MCP server.
        api_key (Optional[SecretStr]): API key for authentication with the MCP server.
        name (str): Name of the MCP server.
        endpoint_path (str): Path to the tools endpoint on the MCP server.
    """

    name: str
    url: HttpUrl
    api_key: Optional[SecretStr] = None
    path: Optional[str] = ""


class RemoteTool(BaseModel):
    """
    Represents a remote tool.

    Attributes:
        name (str): The function to be executed when the tool is called.
        server (MCPServer): The MCP server that provides this tool.
    """

    class RemoteToolType(str, Enum):
        """Enum for different types of remote tools."""

        mcp = "mcp"

    type: RemoteToolType
    name: str
    server: MCPServer

    def is_type_mcp(self) -> bool:
        """
        Check if the remote tool is of type MCP.

        :return: True if the tool is an MCP tool, False otherwise.
        """
        return self.type == self.RemoteToolType.mcp

    @classmethod
    def from_mcp_server(cls, server: MCPServer, tool_name: str) -> "RemoteTool":
        """
        Create a RemoteTool instance from an MCP server and tool name.

        :param server: The MCP server that provides this tool.
        :param tool_name: The name of the tool.
        :return: An instance of RemoteTool.
        """
        return cls(type=cls.RemoteToolType.mcp, name=tool_name, server=server)


__all__ = ["Tool", "FallbackError", "MCPServer", "MCPToolError", "RemoteTool"]
