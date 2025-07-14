"""API as a tool for Nomos."""

from typing import Callable, Dict, Optional, List, TYPE_CHECKING

from pydantic import BaseModel

from .models import ToolDef

METHODS = ["GET", "POST", "PUT", "DELETE", "PATCH", "HEAD", "OPTIONS"]


class APITool(BaseModel):
    """Represents an API tool."""

    name: str
    fn: Callable


class APIWrapper(BaseModel):
    identifier: str
    name: str
    map: Optional[Dict[str, str]] = None
    tool_defs: Optional[Dict[str, ToolDef]] = None

    @property
    def tools(self) -> List[APITool]:
        """Return a list of  api tools defined in the API."""
        method, url = self.split_url(self.identifier)
        if method:
            # TODO: Handle method-specific logic if needed
            return [APITool()]
        tools = []
        for tool_name, endpoint in self.map.items():
            method, endpoint = self.split_url(endpoint)
            url = f"{url}/{endpoint}"
            tools.append(APITool(name=tool_name, fn=lambda: None))

    @staticmethod
    def split_url(url: str) -> tuple[Optional[str], str]:
        """Split a URL into its method (if any) and the base URL."""
        method, rest = url.split("/", 1)
        method = method.upper()
        if method in METHODS:
            return method, rest
        return None, url
