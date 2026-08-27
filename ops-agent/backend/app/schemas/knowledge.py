from pydantic import BaseModel


class KnowledgeDocResponse(BaseModel):
    id: str
    title: str
    chunk_count: int
    source: str | None
    status: str
    created_at: str | None

    class Config:
        from_attributes = True