"""Public entry point for the handbook persistence engine."""

from __future__ import annotations

from pathlib import Path

from handbook.core.folders import resolve_folder
from handbook.core.renderer import Renderer
from handbook.core.storage import StorageEngine
from handbook.exceptions import InvalidItemError
from handbook.models import Algorithm, KnowledgeItem
from handbook.renderers.markdown_renderer import MarkdownRenderer
from handbook.settings import settings


class Handbook:
    """Wires together folder resolution, rendering, and storage.

    Callers never need to know about filenames, directories, templates,
    or duplicate handling -- they just hand over a model::

        hb = Handbook()
        hb.store(Algorithm(title="Binary Exponentiation"))
        hb.store(Problem(title="...", platform="Codeforces", ...))

    Args:
        root: Vault root directory. Defaults to
            :attr:`handbook.settings.settings.vault_path`. Passing this
            explicitly (e.g. a ``tmp_path`` in tests) keeps Handbook
            fully isolated from any real vault or config file.
        renderer: Output-format renderer. Defaults to
            :class:`~handbook.renderers.markdown_renderer.MarkdownRenderer`.
            Swapping in an HTML/JSON/PDF renderer later requires no
            changes to storage or to ``store()``.
    """

    def __init__(
        self, root: Path | str | None = None, renderer: Renderer | None = None
    ):
        self.root = Path(root) if root is not None else settings.vault_path
        self._renderer = renderer if renderer is not None else MarkdownRenderer()
        self._storage = StorageEngine(self.root)

    def store(self, item: KnowledgeItem, *, overwrite: bool = False) -> Path:
        """Persist any KnowledgeItem (Algorithm, Problem, Pattern, Mistake, ...).

        The folder, filename, and metadata (``created_at``/``updated_at``,
        preserving the item's existing ``id``) are all resolved
        automatically -- the caller supplies no path information.

        Args:
            item: The model instance to persist.
            overwrite: If a *different* item already occupies this
                item's title/slug, ``overwrite=True`` replaces it.
                Storing the same ``id`` again is always allowed
                regardless of this flag (see module docs on duplicate
                policy in :mod:`handbook.core.storage`).

        Returns:
            The absolute path the item was written to.

        Raises:
            InvalidItemError: if ``item`` is not a ``KnowledgeItem``.
            DuplicateItemError: on an unresolved title collision.
            StorageError: if a filename can't be derived from the title.
        """
        if not isinstance(item, KnowledgeItem):
            raise InvalidItemError(
                f"store() expects a KnowledgeItem instance, got "
                f"{type(item).__name__!r}."
            )

        folder_name = resolve_folder(item)
        extension = self._renderer.extension

        plan = self._storage.plan(
            item, folder_name=folder_name, extension=extension, overwrite=overwrite
        )
        content = self._renderer.render(plan.item)
        return self._storage.commit(plan, content)

    def create_algorithm(self, title: str, **fields) -> Path:
        """Convenience wrapper over ``store()`` for the common case.

        Delegates entirely to :meth:`store` -- no filesystem logic lives
        here.
        """
        return self.store(Algorithm(title=title, **fields))
