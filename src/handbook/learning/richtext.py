"""Structured inline text.

Every place another format would reach for inline Markdown (``**bold**
text with `code` in it``), this representation uses :class:`RichText`:
an ordered sequence of :class:`Span` objects, each plain text plus a
set of semantic :class:`~handbook.learning.enums.Emphasis` values. This
is what makes the "no Markdown" constraint possible without giving up
formatted text entirely -- the formatting is structured data a
renderer interprets, not syntax embedded in a string a renderer would
have to parse.
"""

from __future__ import annotations

from handbook.learning.enums import Emphasis
from handbook.learning.versioning import LIRModel


class Span(LIRModel):
    """A run of text carrying a uniform set of semantic emphasis.

    Not independently addressable (no id): a span is a fragment of its
    parent ``RichText``, not a citable object in its own right. If a
    future feature needs to point at *exactly this phrase*, that's a
    sign the phrase belongs in its own block, not a highlighted span.
    """

    text: str
    emphasis: tuple[Emphasis, ...] = ()
    link_target: str | None = None
    """An id or a URI this span points at, interpreted by whoever
    resolves it -- may be another ``Page``'s id, a ``Section``'s id, or
    an external URL. This package does not resolve it; it only carries
    the reference, the same "relations as data" philosophy
    ``handbook.models.base.Relation`` uses for the domain model."""


class RichText(LIRModel):
    """An ordered sequence of :class:`Span`, i.e. one run of formatted
    prose."""

    spans: tuple[Span, ...] = ()

    @classmethod
    def plain(cls, text: str) -> RichText:
        """Convenience constructor for the common case: one span, no
        emphasis. ``RichText.plain("just some text")`` instead of
        ``RichText(spans=(Span(text="just some text"),))`` at every
        call site that doesn't need formatting."""
        return cls(spans=(Span(text=text),))

    def as_plain_text(self) -> str:
        """Concatenate every span's text, discarding emphasis.

        For contexts that need a plain string and don't care about
        formatting: search indexing, a title fallback, a debug
        ``repr``. Not a renderer -- it produces no markup of any kind,
        just the bare words.
        """
        return "".join(span.text for span in self.spans)
