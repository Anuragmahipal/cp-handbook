from pydantic import Field

from .base import KnowledgeItem


class Algorithm(KnowledgeItem):
    complexity: str = ""

    intuition: str = ""

    implementation: str = ""

    pitfalls: list[str] = Field(default_factory=list)

    related_problems: list[str] = Field(default_factory=list)
