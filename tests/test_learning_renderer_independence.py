"""A guardrail test: the LIR must never grow a field or nested model
whose name suggests a renderer-specific concept (HTML, Markdown,
Obsidian, CSS, Canvas, React, SVG, PDF) leaking into what is supposed
to be a renderer-independent representation.

This walks ``Page`` and ``LearningPath``'s field trees recursively
rather than checking one class by hand, so it keeps working as new
fields are added -- the point is to make it structurally hard to
accidentally violate the "renderer independent" constraint later, not
just to check today's snapshot of field names.
"""

from __future__ import annotations

import typing

from pydantic import BaseModel

from handbook.learning.page import Page
from handbook.learning.path import LearningPath

_FORBIDDEN_SUBSTRINGS = (
    "html",
    "markdown",
    "obsidian",
    "css",
    "canvas",
    "react",
    "svg",
    "pdf",
)


def _iter_model_classes(model: type[BaseModel], seen: set[type[BaseModel]]) -> None:
    if model in seen:
        return
    seen.add(model)
    for field in model.model_fields.values():
        for candidate in _unwrap(field.annotation):
            if isinstance(candidate, type) and issubclass(candidate, BaseModel):
                _iter_model_classes(candidate, seen)


def _unwrap(annotation: object) -> list[object]:
    """Best-effort unwrap of Optional/Union/tuple/list/Annotated type
    hints down to their leaf types, so nested models inside e.g.
    ``tuple[Block, ...]`` or ``X | None`` are still discovered."""
    args = typing.get_args(annotation)
    if not args:
        return [annotation]
    leaves: list[object] = []
    for arg in args:
        if arg is type(None):
            continue
        leaves.extend(_unwrap(arg))
    return leaves or [annotation]


def _all_field_names(models: set[type[BaseModel]]) -> set[str]:
    names: set[str] = set()
    for model in models:
        names.update(model.model_fields.keys())
    return names


def test_no_forbidden_renderer_concepts_in_page_or_learning_path():
    models: set[type[BaseModel]] = set()
    _iter_model_classes(Page, models)
    _iter_model_classes(LearningPath, models)

    model_names = {model.__name__.lower() for model in models}
    field_names = _all_field_names(models)

    for forbidden in _FORBIDDEN_SUBSTRINGS:
        offending_models = {name for name in model_names if forbidden in name}
        offending_fields = {name for name in field_names if forbidden in name}
        assert not offending_models, (
            f"{forbidden!r} found in model names: {offending_models}"
        )
        assert not offending_fields, (
            f"{forbidden!r} found in field names: {offending_fields}"
        )
