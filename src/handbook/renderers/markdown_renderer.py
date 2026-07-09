"""Markdown renderer: the first (and currently only) concrete Renderer.

Types with a dedicated Jinja template (currently just ``Algorithm``) get
their full templated layout. Any other ``KnowledgeItem`` still renders
correctly through a generic YAML-frontmatter fallback, so
``Handbook.store()`` works uniformly across every knowledge type even
before it has a bespoke template of its own.
"""

from __future__ import annotations

import yaml

from handbook.core.renderer import Renderer
from handbook.models import Algorithm, KnowledgeItem
from handbook.template_engine import render as render_jinja_template


class MarkdownRenderer(Renderer):
    """Renders KnowledgeItems as Markdown with YAML frontmatter."""

    extension = ".md"

    _TEMPLATES: dict[type[KnowledgeItem], str] = {
        Algorithm: "algorithms/algorithm.md.j2",
    }

    def render(self, item: KnowledgeItem) -> str:
        template_name = self._template_for(type(item))
        if template_name is not None:
            return render_jinja_template(template_name, **item.model_dump(mode="json"))
        return self._render_generic(item)

    def _template_for(self, cls: type[KnowledgeItem]) -> str | None:
        for klass in cls.__mro__:
            template_name = self._TEMPLATES.get(klass)
            if template_name is not None:
                return template_name
        return None

    def _render_generic(self, item: KnowledgeItem) -> str:
        """Fallback used for any KnowledgeItem without a dedicated template.

        Produces valid, parseable Markdown (YAML frontmatter + a heading)
        so every current and future knowledge type is persistable from
        day one, without needing storage or Handbook to know it exists.
        """
        data = item.model_dump(mode="json")
        frontmatter = yaml.safe_dump(data, allow_unicode=True, sort_keys=False)
        return f"---\n{frontmatter}---\n\n# {item.title}\n"
