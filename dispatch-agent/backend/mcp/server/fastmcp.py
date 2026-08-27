"""Mock FastMCP - provides a compatible interface for local development."""
import logging
from typing import Callable, Any
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class Tool:
    """Tool descriptor - uses dataclass to avoid bound method issues."""
    name: str
    fn: Callable
    description: str = ""


class ToolManager:
    """Mock tool manager that stores registered tools."""
    def __init__(self):
        self._tools: dict[str, Tool] = {}

    def register(self, name: str, fn: Callable, description: str = ""):
        # Use a wrapper to avoid the function becoming a bound method
        self._tools[name] = Tool(name=name, fn=fn, description=description)
        return fn


class FastMCP:
    """Mock FastMCP server compatible with the real MCP SDK."""
    def __init__(self, name: str):
        self.name = name
        self._tool_manager = ToolManager()
        self._resources: dict[str, Callable] = {}

    def tool(self, name: str = None, description: str = ""):
        """Decorator to register a tool."""
        def decorator(fn: Callable):
            tool_name = name or fn.__name__
            self._tool_manager.register(tool_name, fn, description)
            return fn
        return decorator

    def resource(self, uri: str):
        """Decorator to register a resource."""
        def decorator(fn: Callable):
            self._resources[uri] = fn
            return fn
        return decorator