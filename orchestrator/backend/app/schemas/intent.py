from pydantic import BaseModel
from typing import Optional


class IntentResult(BaseModel):
    intent: str
    target_agent: str
    confidence: Optional[float] = None


class IntentClassifyRequest(BaseModel):
    message: str