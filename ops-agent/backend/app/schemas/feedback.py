from pydantic import BaseModel


class FeedbackRequest(BaseModel):
    message_id: str
    feedback: str  # helpful / unhelpful