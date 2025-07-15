"""API as a tool for Nomos."""

import re
from typing import Dict, List, Optional

import requests
from pydantic import BaseModel

from .models import ToolDef

METHODS = ["GET", "POST", "PUT", "DELETE", "PATCH", "HEAD", "OPTIONS"]


class APITool(BaseModel):
    """Represents an API tool."""

    name: str
    url: str
    method: str
    headers: Optional[Dict[str, str]] = None

    def run(self, **kwargs) -> str:
        """Run the API tool."""
        body = kwargs.pop("body", None)
        headers = self.headers or {}
        if body is not None:
            headers["Content-Type"] = "application/json"
        url_params = re.findall(r"\{([^}]+)\}", self.url)
        url_copy = self.url
        for param in url_params:
            if param in kwargs:
                url_copy = url_copy.replace(f"{{{param}}}", str(kwargs[param]))
                del kwargs[param]
            else:
                raise ValueError(f"Missing required parameter: {param}")
        response = requests.request(
            method=self.method,
            url=url_copy,
            json=body,
            headers=headers,
            params=kwargs,
        )
        response.raise_for_status()
        return response.text


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
            assert method in METHODS, f"Invalid method '{method}' in identifier '{self.identifier}'"
            return [APITool(name=self.name, url=url, method=method)]
        tools = []
        assert self.map is not None, "API map must be defined"
        for tool_name, endpoint in self.map.items():
            method, endpoint = self.split_url(endpoint)
            assert method is not None and method in METHODS, (
                f"Invalid method '{method}' in endpoint '{endpoint}'"
            )
            _url = f"{url}/{endpoint}"
            tools.append(APITool(name=tool_name, url=_url, method=method))
        return tools

    @staticmethod
    def split_url(url: str) -> tuple[Optional[str], str]:
        """Split a URL into its method (if any) and the base URL."""
        url = url.lstrip("/")
        method, rest = url.split("/", 1)
        method = method.upper()
        if method in METHODS:
            return method, rest
        return None, url
