"""Tool definitions for Nomos."""

from typing import List, Optional, Type

from pydantic import BaseModel

from ..utils.utils import parse_type

class ArgDef(BaseModel):
    """Documentation for an argument of a tool."""

    key: str  # Name of the argument
    desc: Optional[str] = None  # Description of the argument
    type: Optional[str] = (
        None  # Type of the argument (e.g., "str", "int", "float", "bool", "List[str]", etc.)
    )

    def get_type(self) -> Optional[Type]:
        return parse_type(self.type) if self.type else None


class ToolDef(BaseModel):
    """Documentation for a tool."""

    desc: Optional[str] = None  # Description of the tool
    args: List[ArgDef]  # Argument descriptions for the tool