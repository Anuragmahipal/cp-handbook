"""``RenderResult``: what a renderer produces, independent of what kind
of renderer produced it.

Deliberately not notebook-specific despite living in this package for
now -- ``html``/``css``/``assets`` is a shape a slide renderer or a
flashcard renderer could return just as easily (a slide deck's
``html`` might be a ``<section>`` per slide instead of a notebook
page; ``assets`` exists today as an empty seam for the day a renderer
needs to ship a font file or an icon alongside its markup). If a
second renderer is ever built, this is the type to lift out to a
shared location -- not duplicated per renderer.
"""

from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel, ConfigDict

from handbook.utils.filesystem import atomic_write


class RenderResult(BaseModel):
    """The output of rendering one page: a standalone HTML document,
    its stylesheet (both combined into ``html`` via an inline
    ``<style>`` tag, and also exposed separately for programmatic
    reuse), and any binary assets it references.
    """

    model_config = ConfigDict(frozen=True)

    title: str
    html: str
    """A complete, standalone HTML document -- opening it directly in
    a browser (no server, no build step) reproduces the full page,
    including styling."""
    css: str
    """The stylesheet, already inlined into ``html``'s ``<style>``
    tag. Exposed separately so a caller that wants to reuse the same
    visual language across several pages (a shared stylesheet file)
    doesn't have to extract it by parsing ``html`` back out."""
    assets: dict[str, bytes] = {}
    """Binary assets (fonts, icons) this render references by name.
    Empty today -- everything currently in this renderer is inline SVG
    and CSS, so nothing external is needed yet."""

    def write(self, directory: Path, *, filename: str = "output.html") -> Path:
        """Write ``html`` to ``directory / filename`` and any
        ``assets`` alongside it. Returns the path written to.

        Uses the same atomic-write primitive
        ``handbook.core.storage.StorageEngine`` uses, without going
        through ``StorageEngine`` itself -- this writes a rendered
        *artifact* for a person to open in a browser, not a
        knowledge-base entry for :class:`~handbook.core.storage.
        StorageEngine` to track and deduplicate.
        """
        target = Path(directory) / filename
        atomic_write(target, self.html)
        for asset_name, data in self.assets.items():
            (Path(directory) / asset_name).write_bytes(data)
        return target
