"""Utility functions and helpers for the Nomos package."""

import ast
from enum import Enum
from typing import TYPE_CHECKING, Any, Dict, List, Literal, Optional, Tuple, Type, Union

from pydantic import BaseModel, ConfigDict, Field, create_model

if TYPE_CHECKING:
    from ..models.agent import Step
    from ..models.flow import Flow
    from ..models.tool import Tool


def create_base_model(
    name: str, params: Dict[str, Dict[str, Any]], desc: Optional[str] = None
) -> Type[BaseModel]:
    """
    Dynamically create a Pydantic BaseModel with the given name and fields.

    :param name: Name of the model.
    :param params: Dictionary of field names to type/config dicts. Each config dict should have:
        - 'type': The type of the field.
        - 'default' (optional): The default value for the field.
        - 'description' (optional): The field description.
        - 'optional' (optional): Whether the field is optional (default: False).
        - 'is_list' (optional): Whether the field is a list (default: False).
    :return: A dynamically created Pydantic BaseModel subclass.
    """
    fields = {}
    for field_name, config in params.items():
        field_type = config["type"]
        default_val = config.get("default", ...)
        description = config.get("description")
        is_optional = config.get("optional", False)
        is_list = config.get("is_list", False)

        if isinstance(field_type, dict):
            field_type = create_base_model(
                name=field_type.get("name", "DynamicModel"),
                params=field_type.get("params", {}),
            )
        elif isinstance(field_type, list):
            field_types = []
            for _, item in enumerate(field_type):
                nested_field_type = create_base_model(
                    name=item.get("name", "DynamicModel"),
                    params=item.get("params", {}),
                )
                field_types.append(nested_field_type)
            field_type = Union.__getitem__(tuple(field_types))

        if is_list:
            field_type = List[field_type]  # type: ignore
        if is_optional:
            field_type = Optional[field_type]

        if description is not None and description != "":
            field_info = Field(default=default_val, description=description)
        else:
            field_info = default_val

        fields[field_name] = (field_type, field_info)

    return create_model(name, **fields, __config__=ConfigDict(extra="ignore"), __doc__=desc)


def create_enum(name: str, values: Dict[str, Any]) -> Enum:
    """
    Dynamically create an Enum class with the given name and values.

    :param name: Name of the enum.
    :param values: Dictionary of enum member names to values.
    :return: A dynamically created Enum class.
    """
    return Enum(name, values)


def convert_camelcase_to_snakecase(name: str) -> str:
    """Convert a camelCase or PascalCase string to snake_case."""
    return "".join(["_" + i.lower() if i.isupper() else i for i in name]).lstrip("_")


def parse_type(type_str: str) -> type:
    """Safely parse type strings without eval/exec."""
    # Type mapping
    TYPE_MAP = {
        "str": str,
        "bool": bool,
        "int": int,
        "float": float,
        "Dict": Dict,
        "List": List,
        "Tuple": Tuple,
        "Union": Union,
        "Literal": Literal,
        "Optional": Optional,
        "integer": int,
        "string": str,
        "boolean": bool,
        "number": float,
        "array": List,
        "object": Dict,
    }

    def parse_expression(node) -> Any:  # noqa
        if isinstance(node, ast.Name):
            return TYPE_MAP.get(node.id, getattr(__builtins__, node.id, None))
        elif isinstance(node, ast.Subscript):
            base = parse_expression(node.value)
            if isinstance(node.slice, ast.Tuple):
                args = tuple(parse_expression(elt) for elt in node.slice.elts)
            else:
                args = (parse_expression(node.slice),)
            return base[args] if len(args) > 1 else base[args[0]]
        elif isinstance(node, ast.Constant):
            return node.value
        else:
            raise ValueError(f"Unsupported node type: {type(node)}")

    try:
        tree = ast.parse(type_str, mode="eval")
        return parse_expression(tree.body)
    except Exception as e:
        raise ValueError(f"Invalid type: {type_str}") from e


def create_mermaid_graph(
    steps: dict[str, "Step"], tools: dict[str, "Tool"], flows: list["Flow"]
) -> str:
    """Generate a Mermaid graph representation of the steps, tools, and flows."""
    mermaid_graph = "graph TD\n"

    # Track which steps belong to flows
    flow_steps = set()

    # Create subgroups for each flow
    for flow in flows:
        if flow.steps:  # Only create subgroup if flow has steps
            mermaid_graph += f'\n    subgraph flow_{flow.flow_id}["{flow.flow_id}"]\n'

            # Add steps within this flow as nodes
            for step_id, step in flow.steps.items():
                mermaid_graph += (
                    f'        step_{step_id}["<b>{step_id}</b><br/>{step.description[:30]}"]\n'
                )
                flow_steps.add(step_id)

            mermaid_graph += "    end\n"

    # Add any remaining steps that don't belong to flows
    for step_id, step in steps.items():
        if step_id not in flow_steps:
            mermaid_graph += f'step_{step_id}["<b>{step_id}</b><br/>{step.description[:30]}"]\n'

    # Add routes between steps
    for step_id, step in steps.items():
        for route in step.routes:
            mermaid_graph += f"step_{step_id} -->|{route.condition}| step_{route.target}\n"

    # Add tools as nodes with different styling
    for tool_name, tool in tools.items():
        mermaid_graph += f'tool_{tool_name}["<b>{tool_name}</b><br/>{tool.description[:25]}"]\n'

    # Style the tool nodes with different color
    mermaid_graph += "\n    %% Tool styling\n"
    for tool_name in tools.keys():
        mermaid_graph += f"    tool_{tool_name}:::toolStyle\n"

    mermaid_graph += (
        "    classDef toolStyle fill:#e8f4fd,stroke:#1e88e5,stroke-width:2px,color:#000\n"
    )

    # Add connections from steps to their available tools
    for step_id, step in steps.items():
        if step.available_tools:
            for tool_name in step.available_tools:
                if tool_name in tools:
                    mermaid_graph += f"step_{step_id} -->|uses| tool_{tool_name}\n"

    return mermaid_graph


def mermaid_svg(graph: str, save_to: Optional[str] = None, display: bool = True):
    """Generate and optionally display a Mermaid graph as SVG."""
    import base64
    from urllib.request import Request, urlopen

    graphbytes = graph.encode()
    base64_bytes = base64.b64encode(graphbytes)
    base64_string = base64_bytes.decode()
    url = "https://mermaid.ink/svg/" + base64_string
    req = Request(url, headers={"User-Agent": "IPython/Notebook"})
    svg = urlopen(req).read().decode()

    if save_to:
        with open(save_to, "w") as f:
            f.write(svg)
    if display:
        from IPython.display import display_svg

        display_svg(svg, raw=True)


__all__ = [
    "create_base_model",
    "create_enum",
    "convert_camelcase_to_snakecase",
    "parse_type",
]
