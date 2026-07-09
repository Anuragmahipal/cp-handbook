from pydantic import Field

from .base import KnowledgeItem


class Pattern(KnowledgeItem):
    description: str = ""

    related_algorithms: list[str] = Field(default_factory=list)

