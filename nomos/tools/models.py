"""Tool definitions for Nomos."""

from typing import List, Optional, Type, Union

from pydantic import BaseModel

from ..utils.utils import parse_type


class ArgDef(BaseModel):
    """Documentation for an argument of a tool."""

    key: str  # Name of the argument
    desc: Optional[str] = None  # Description of the argument
    type: Optional[str] = (
        None  # Type of the argument (e.g., "str", "int", "float", "bool", "List[str]", etc.)
    )
    default: Optional[Union[str, int, float, bool]] = None  # Default value of the argument

    def get_type(self) -> Optional[Type]:
        return parse_type(self.type) if self.type else None


class ToolDef(BaseModel):
    """Documentation for a tool."""

    desc: Optional[str] = None  # Description of the tool
    args: List[ArgDef]  # Argument descriptions for the tool

    def get_args(self) -> dict:
        """Return a dictionary of argument names to their types and descriptions."""
        return {
            arg.key: {
                "type": arg.get_type(),
                "description": arg.desc or "",
                "default": arg.default,
            }
            for arg in self.args
        }
