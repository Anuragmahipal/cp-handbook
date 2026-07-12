"""``NotebookTheme``: the design tokens that give a rendered notebook
page its look, decoupled from the layout/markup logic that uses them.

A theme is a flat set of named tokens (colors, fonts, spacing) — never
markup, never CSS selectors. ``css_template.build()`` is the only place
that knows how a token turns into an actual CSS rule; a new theme is
just a new set of values for the same tokens, which is what makes
"Dark" or "Handwritten" cheap to add without touching the renderer or
the CSS generator at all.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class NotebookTheme(BaseModel):
    """A named set of visual design tokens for the notebook renderer."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    name: str

    # -- surfaces -------------------------------------------------------
    page_background: str
    card_background: str
    card_border: str

    # -- text -------------------------------------------------------------
    ink: str
    """Primary text color."""
    ink_muted: str
    """Secondary text: captions, metadata, timestamps."""
    accent: str
    """The single accent color used for emphasis: current-focus
    highlights, active pointers, the review-cue "DUE" badge."""

    # -- typography ---------------------------------------------------------
    heading_font: str
    body_font: str
    code_font: str

    # -- callouts (one background/border pair per CalloutKind value) --------
    callout_colors: dict[str, tuple[str, str]]
    """Maps a ``CalloutKind`` value (e.g. ``"tip"``) to a
    ``(background, border)`` color pair. Every ``CalloutKind`` member
    must have an entry -- see :meth:`NotebookTheme.model_post_init`."""

    # -- review cues (one color per ReviewStatus value) ----------------------
    review_colors: dict[str, str]
    """Maps a ``ReviewStatus`` value to a badge color."""

    # -- code syntax highlighting -----------------------------------------
    syntax_colors: dict[str, str]
    """Maps a token kind (``"keyword"``, ``"string"``, ``"comment"``,
    ``"number"``, ``"preprocessor"``) to a color."""

    # -- diagram ------------------------------------------------------------
    diagram_node_fill: str
    diagram_node_stroke: str
    diagram_edge_stroke: str
    diagram_emphasis_stroke: str

    corner_radius: int = 10
    """Shared rounding, in pixels, for cards, callouts, and diagram
    boxes -- one token instead of a magic number repeated in three
    places."""

    def model_post_init(self, __context: object) -> None:
        from handbook.learning.enums import CalloutKind, ReviewStatus

        missing_callouts = {k.value for k in CalloutKind} - set(self.callout_colors)
        if missing_callouts:
            raise ValueError(
                f"NotebookTheme {self.name!r} is missing callout_colors "
                f"for: {sorted(missing_callouts)}"
            )
        missing_review = {s.value for s in ReviewStatus} - set(self.review_colors)
        if missing_review:
            raise ValueError(
                f"NotebookTheme {self.name!r} is missing review_colors "
                f"for: {sorted(missing_review)}"
            )

    # -- built-in presets ---------------------------------------------------

    @classmethod
    def light_notebook(cls) -> NotebookTheme:
        """The default theme: a bright, high-contrast paper-like page."""
        return cls(
            name="Light Notebook",
            page_background="#f7f3ea",
            card_background="#ffffff",
            card_border="#e4ddc9",
            ink="#2b2620",
            ink_muted="#8a8172",
            accent="#c65d2e",
            heading_font="'Iowan Old Style', 'Georgia', serif",
            body_font="'Iowan Old Style', 'Georgia', serif",
            code_font="'SFMono-Regular', 'Menlo', 'Consolas', monospace",
            callout_colors={
                "tip": ("#eaf5ec", "#7fb08a"),
                "warning": ("#fdf1de", "#d99a3c"),
                "pitfall": ("#fdeeee", "#cf6a6a"),
                "insight": ("#eef2fb", "#6d84c9"),
                "definition": ("#f3eef8", "#9b7bc4"),
                "example": ("#eef8f7", "#5aa9a1"),
                "mistake": ("#fdeaea", "#c94f4f"),
                "question": ("#fef8e6", "#c9a63a"),
            },
            review_colors={
                "new": "#8a8172",
                "learning": "#c9a63a",
                "due": "#c65d2e",
                "mastered": "#5a9a6f",
                "suspended": "#a8a196",
            },
            syntax_colors={
                "keyword": "#8a3ea8",
                "string": "#3f8f5f",
                "comment": "#9a9284",
                "number": "#c65d2e",
                "preprocessor": "#b2456e",
            },
            diagram_node_fill="#fffdf7",
            diagram_node_stroke="#c9bfa3",
            diagram_edge_stroke="#8a8172",
            diagram_emphasis_stroke="#c65d2e",
        )

    @classmethod
    def dark_notebook(cls) -> NotebookTheme:
        """A dark-surface variant of the same design language."""
        return cls(
            name="Dark Notebook",
            page_background="#1c1a17",
            card_background="#26231e",
            card_border="#3c3831",
            ink="#ece6d8",
            ink_muted="#948b7a",
            accent="#e08a52",
            heading_font="'Iowan Old Style', 'Georgia', serif",
            body_font="'Iowan Old Style', 'Georgia', serif",
            code_font="'SFMono-Regular', 'Menlo', 'Consolas', monospace",
            callout_colors={
                "tip": ("#203028", "#5f9c72"),
                "warning": ("#332a1a", "#c99248"),
                "pitfall": ("#341f1f", "#b56464"),
                "insight": ("#1f2434", "#7186c4"),
                "definition": ("#291f34", "#9a79bd"),
                "example": ("#1c2f2d", "#5fa89f"),
                "mistake": ("#331e1e", "#c05a5a"),
                "question": ("#332c19", "#c2a145"),
            },
            review_colors={
                "new": "#948b7a",
                "learning": "#c2a145",
                "due": "#e08a52",
                "mastered": "#6fb083",
                "suspended": "#665f54",
            },
            syntax_colors={
                "keyword": "#c795e3",
                "string": "#83c99b",
                "comment": "#7d7565",
                "number": "#e08a52",
                "preprocessor": "#e089ab",
            },
            diagram_node_fill="#2c2820",
            diagram_node_stroke="#524b3d",
            diagram_edge_stroke="#948b7a",
            diagram_emphasis_stroke="#e08a52",
        )

    @classmethod
    def handwritten(cls) -> NotebookTheme:
        """A softer, warmer variant leaning into the "handwritten study
        notes" brief -- a cream page, a marker-style accent, and a
        rounder corner radius."""
        return cls(
            name="Handwritten",
            page_background="#fbf6e9",
            card_background="#fffef9",
            card_border="#e8dcb0",
            ink="#3a3120",
            ink_muted="#8f7f56",
            accent="#2f6fb0",
            heading_font="'Bradley Hand', 'Comic Sans MS', cursive",
            body_font="'Bradley Hand', 'Comic Sans MS', cursive",
            code_font="'SFMono-Regular', 'Menlo', 'Consolas', monospace",
            callout_colors={
                "tip": ("#eef7e4", "#7fae4d"),
                "warning": ("#fdf0dd", "#e0a233"),
                "pitfall": ("#fdeaea", "#d9686e"),
                "insight": ("#e9f1fc", "#2f6fb0"),
                "definition": ("#f4edfa", "#8f5fc4"),
                "example": ("#e9f8f2", "#2f9e82"),
                "mistake": ("#fde6e6", "#d1494f"),
                "question": ("#fdf6da", "#cc9f1f"),
            },
            review_colors={
                "new": "#8f7f56",
                "learning": "#cc9f1f",
                "due": "#d1494f",
                "mastered": "#4f9e6d",
                "suspended": "#b2a684",
            },
            syntax_colors={
                "keyword": "#8f5fc4",
                "string": "#2f9e82",
                "comment": "#a2916a",
                "number": "#2f6fb0",
                "preprocessor": "#d1497e",
            },
            diagram_node_fill="#fffef9",
            diagram_node_stroke="#d8c98a",
            diagram_edge_stroke="#8f7f56",
            diagram_emphasis_stroke="#2f6fb0",
            corner_radius=16,
        )
