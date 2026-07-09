from pydantic import Field

from .base import KnowledgeItem


class Problem(KnowledgeItem):
    platform: str

    contest: str

    index: str

    url: str = ""

    rating: int | None = None

    algorithms: list[str] = Field(default_factory=list)

    patterns: list[str] = Field(default_factory=list)

    mistakes: list[str] = Field(default_factory=list)

    solved: bool = True
