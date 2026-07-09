from datetime import datetime
from uuid import uuid4

from pydantic import BaseModel, Field


class KnowledgeItem(BaseModel):
    """
    Base class for every knowledge item in the handbook.
    """

    id: str = Field(default_factory=lambda: str(uuid4()))

    title: str

    tags: list[str] = Field(default_factory=list)

    aliases: list[str] = Field(default_factory=list)

    created_at: datetime = Field(default_factory=datetime.now)

    updated_at: datetime = Field(default_factory=datetime.now)
