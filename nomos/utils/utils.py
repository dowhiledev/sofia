"""Utility functions and helpers for the Nomos package."""

import ast
from enum import Enum
from typing import Any, Dict, List, Literal, Optional, Tuple, Type, Union

from pydantic import BaseModel, ConfigDict, Field, create_model


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


__all__ = [
    "create_base_model",
    "create_enum",
    "convert_camelcase_to_snakecase",
    "parse_type",
]
