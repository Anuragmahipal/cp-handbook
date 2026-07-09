"""Renderer interface: turning a KnowledgeItem into a persistable string.

StorageEngine only ever sees the resulting string that a Renderer
produces -- it has no idea whether that string is Markdown, HTML, or
JSON. Adding a new output format means writing one new Renderer
subclass; storage never has to change.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from handbook.models import KnowledgeItem


class Renderer(ABC):
    """Abstract base for all output-format renderers."""

    extension: str
    """File extension for this format, including the leading dot (e.g. ``.md``)."""

    @abstractmethod
    def render(self, item: KnowledgeItem) -> str:
        """Return the full string representation of ``item`` in this format."""
        raise NotImplementedError
