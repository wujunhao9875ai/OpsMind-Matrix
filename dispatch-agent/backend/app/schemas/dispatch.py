from pydantic import BaseModel, Field
from typing import Optional, Literal
from datetime import datetime


class TicketCreate(BaseModel):
    title: str = Field(..., max_length=500)
    description: str = ""
    fault_category: Literal["hardware", "software", "network", "other"] = "other"
    urgency: Literal["low", "medium", "high", "critical"] = "medium"
    device_info: Optional[dict] = None
    location: Optional[str] = None
    engineer_id: Optional[str] = None


class TicketAssign(BaseModel):
    engineer_id: Optional[str] = None


class TicketReassign(BaseModel):
    engineer_id: str
    reason: Optional[str] = None


class TicketReject(BaseModel):
    reason: Optional[str] = None
    suggest_engineer_id: Optional[str] = None


class TicketTransfer(BaseModel):
    target_engineer_id: str
    reason: Optional[str] = None


class TicketUpdate(BaseModel):
    """Engineer corrects ticket info after on-site inspection"""
    fault_category: Optional[Literal["hardware", "software", "network", "other"]] = None
    urgency: Optional[Literal["low", "medium", "high", "critical"]] = None
    description: Optional[str] = None
    device_info: Optional[dict] = None
    location: Optional[str] = None
    correction_note: Optional[str] = None


class TicketResolve(BaseModel):
    resolution: str


class TicketReopen(BaseModel):
    reason: Optional[str] = None


class TicketCancel(BaseModel):
    reason: Optional[str] = None


class TicketPriorityChange(BaseModel):
    urgency: Literal["low", "medium", "high", "critical"]


class EngineerCreate(BaseModel):
    user_id: str
    display_name: str
    skills: list[str] = []
    skill_levels: dict = {}


class EngineerSkillUpdate(BaseModel):
    skills: list[str]
    skill_levels: dict = {}


class EngineerStatusUpdate(BaseModel):
    status: str
    location: Optional[str] = None


class TicketResponse(BaseModel):
    id: str
    ticket_no: str
    title: str
    description: str
    fault_category: str
    urgency: str
    device_info: Optional[dict] = None
    location: Optional[str] = None
    status: str
    assigned_to: Optional[str] = None
    assigned_at: Optional[datetime] = None
    resolution: Optional[str] = None
    resolved_at: Optional[datetime] = None
    closed_at: Optional[datetime] = None
    sla_deadline: Optional[datetime] = None
    created_by: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class TicketListResponse(BaseModel):
    total: int
    page: int
    page_size: int
    items: list[TicketResponse]


class EngineerResponse(BaseModel):
    id: str
    user_id: str
    display_name: str
    skills: list[str]
    skill_levels: dict
    status: str
    location: Optional[str] = None
    last_location: Optional[str] = None
    max_concurrent: int
    current_load: int
    total_completed: int
    avg_resolution_minutes: float
    rating: float


class EngineerListResponse(BaseModel):
    total: int
    items: list[EngineerResponse]


class TicketLogResponse(BaseModel):
    id: str
    action: str
    operator_id: Optional[str] = None
    from_status: Optional[str] = None
    to_status: Optional[str] = None
    comment: Optional[str] = None
    extra_data: Optional[dict] = None
    created_at: Optional[datetime] = None