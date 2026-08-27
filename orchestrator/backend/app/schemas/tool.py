from pydantic import BaseModel
from typing import Optional, Any


class ToolCallRequest(BaseModel):
    agent_name: str
    tool_name: str
    arguments: dict = {}


class ToolCallResponse(BaseModel):
    success: bool
    data: Optional[Any] = None
    error: Optional[str] = None
    degraded: bool = False


class ToolInfo(BaseModel):
    name: str
    description: Optional[str] = None
    parameters: Optional[dict] = None


class AgentInfo(BaseModel):
    name: str
    tools: list[str]
    status: str