"""Builds the complete stylesheet for a rendered page from a
``NotebookTheme``.

The only place in this renderer that knows CSS syntax. Every class
name used here is also the class name ``blocks_html``/``svg``/
``renderer`` emit -- there is exactly one source of truth for the
visual language (this file) and exactly one source of truth for the
markup structure (everywhere else), and they agree only by both
referencing the same fixed set of class names.
"""

from __future__ import annotations

from handbook.learning.enums import CalloutKind, ReviewStatus
from handbook.renderers.notebook.theme import NotebookTheme


def _callout_rules(theme: NotebookTheme) -> str:
    rules = []
    for kind in CalloutKind:
        background, border = theme.callout_colors[kind.value]
        rules.append(
            f".lir-callout-{kind.value} {{"
            f"background:{background}; border-color:{border};"
            "}"
        )
    return "\n".join(rules)


def _review_rules(theme: NotebookTheme) -> str:
    rules = []
    for status in ReviewStatus:
        color = theme.review_colors[status.value]
        rules.append(f".lir-review-{status.value} {{ background:{color}; }}")
    return "\n".join(rules)


def build(theme: NotebookTheme) -> str:
    """Return the full stylesheet, as one CSS string, for ``theme``."""
    r = theme.corner_radius
    return f"""
:root {{
  color-scheme: {"dark" if "Dark" in theme.name else "light"};
}}

* {{ box-sizing: border-box; }}

body.lir-page {{
  margin: 0;
  padding: 48px 24px 96px;
  background: {theme.page_background};
  color: {theme.ink};
  font-family: {theme.body_font};
  line-height: 1.55;
}}

.lir-container {{
  max-width: 980px;
  margin: 0 auto;
}}

/* -- header ------------------------------------------------------- */

.lir-header {{
  margin-bottom: 40px;
}}

.lir-title {{
  font-family: {theme.heading_font};
  font-size: 2.4rem;
  margin: 0 0 6px;
}}

.lir-summary {{
  color: {theme.ink_muted};
  font-size: 1.05rem;
  margin: 0 0 14px;
  max-width: 62ch;
}}

.lir-metadata {{
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  align-items: center;
}}

.lir-meta-chip, .lir-tag {{
  font-size: 0.78rem;
  padding: 3px 10px;
  border-radius: 999px;
  border: 1px solid {theme.card_border};
  color: {theme.ink_muted};
  background: {theme.card_background};
}}

.lir-meta-chip-accent {{
  border-color: {theme.accent};
  color: {theme.accent};
}}

/* -- path strip ----------------------------------------------------- */

.lir-path-strip {{
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  align-items: center;
  margin-bottom: 28px;
  font-size: 0.82rem;
  color: {theme.ink_muted};
}}

.lir-path-step {{
  padding: 3px 10px;
  border-radius: 999px;
  border: 1px solid {theme.card_border};
}}

.lir-path-step-current {{
  border-color: {theme.accent};
  color: {theme.accent};
  font-weight: 600;
}}

/* -- rows / cards --------------------------------------------------- */

.lir-row {{
  display: flex;
  flex-wrap: wrap;
  gap: 20px;
  margin-bottom: 20px;
  padding-top: 20px;
  border-top: 1px solid {theme.card_border};
}}

.lir-row:first-of-type {{
  border-top: none;
  padding-top: 0;
}}

.lir-card {{
  flex: 1 1 260px;
  background: {theme.card_background};
  border: 1px solid {theme.card_border};
  border-radius: {r}px;
  padding: 22px 24px;
  box-shadow: 0 1px 3px rgba(0,0,0,0.06);
}}

.lir-section-heading {{
  font-family: {theme.heading_font};
  font-size: 1.15rem;
  margin: 0 0 12px;
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}}

/* -- text ------------------------------------------------------------ */

.lir-text {{ margin: 0 0 12px; }}
.lir-text:last-child {{ margin-bottom: 0; }}
.lir-text-intuition {{ font-size: 1.05rem; }}
.lir-text-summary {{ color: {theme.ink_muted}; font-style: italic; }}
.lir-text-caption {{ font-size: 0.85rem; color: {theme.ink_muted}; }}

/* -- code ------------------------------------------------------------ */

.lir-code-block {{ margin: 12px 0; }}
.lir-code-caption {{
  font-size: 0.8rem;
  color: {theme.ink_muted};
  margin-bottom: 6px;
}}
table.lir-code {{
  width: 100%;
  border-collapse: collapse;
  font-family: {theme.code_font};
  font-size: 0.86rem;
  background: {theme.page_background};
  border-radius: {r}px;
  overflow: hidden;
}}
.lir-code-row-highlighted {{ background: {theme.card_border}; }}
.lir-code-lineno {{
  width: 1%;
  text-align: right;
  color: {theme.ink_muted};
  padding: 1px 10px;
  user-select: none;
  opacity: 0.6;
}}
.lir-code-line {{ padding: 1px 10px; white-space: pre; }}
.lir-code-note {{
  padding: 1px 10px;
  color: {theme.ink_muted};
  font-family: {theme.body_font};
  font-size: 0.78rem;
  font-style: italic;
  white-space: normal;
}}
.tok-kw {{ color: {theme.syntax_colors["keyword"]}; font-weight: 600; }}
.tok-str {{ color: {theme.syntax_colors["string"]}; }}
.tok-com {{ color: {theme.syntax_colors["comment"]}; font-style: italic; }}
.tok-num {{ color: {theme.syntax_colors["number"]}; }}
.tok-pre {{ color: {theme.syntax_colors["preprocessor"]}; }}

/* -- callouts --------------------------------------------------------- */

.lir-callout {{
  border: 1px solid;
  border-left-width: 4px;
  border-radius: {r}px;
  padding: 14px 16px;
  margin: 12px 0;
}}
.lir-callout-title {{ font-weight: 700; margin-bottom: 4px; }}
.lir-callout-body .lir-text {{ margin: 0; }}
{_callout_rules(theme)}

/* -- diagrams ---------------------------------------------------------- */

.lir-diagram-block {{ margin: 12px 0; }}
svg.lir-diagram {{ width: 100%; height: auto; display: block; }}
.lir-diagram-caption {{
  font-size: 0.8rem;
  color: {theme.ink_muted};
  margin-top: 6px;
}}
text.lir-node-label, text.lir-node-caption {{
  font-family: {theme.body_font};
  font-size: 12px;
  fill: {theme.ink};
}}
text.lir-node-value {{
  font-family: {theme.code_font};
  font-size: 15px;
  font-weight: 700;
  fill: {theme.ink};
}}
text.lir-edge-label {{
  font-family: {theme.body_font};
  font-size: 10.5px;
  fill: {theme.ink_muted};
}}
text.lir-step-badge {{
  font-family: {theme.body_font};
  font-size: 10px;
  fill: {theme.card_background};
  font-weight: 700;
}}

/* -- visual chips (standalone VisualBlock) ----------------------------- */

.lir-visual-chip {{
  display: inline-flex;
  flex-direction: column;
  align-items: center;
  gap: 2px;
  border: 1.5px solid {theme.diagram_node_stroke};
  background: {theme.diagram_node_fill};
  border-radius: {r}px;
  padding: 8px 14px;
  margin: 4px 6px 4px 0;
}}
.lir-visual-chip-emphasis {{
  border-color: {theme.diagram_emphasis_stroke};
  border-width: 2.5px;
}}
.lir-visual-chip-value {{ font-family: {theme.code_font}; font-weight: 700; }}
.lir-visual-chip-label {{ font-size: 0.78rem; color: {theme.ink_muted}; }}

/* -- memory anchors (sticky-note style) --------------------------------- */

.lir-anchor {{
  display: flex;
  flex-direction: column;
  gap: 4px;
  background: color-mix(in srgb, {theme.accent} 12%, {theme.card_background});
  border: 1px solid {theme.accent};
  border-radius: {r}px;
  padding: 10px 14px;
  margin: 10px 6px 4px 0;
  max-width: 320px;
  transform: rotate(-0.6deg);
}}
.lir-anchor-kicker {{
  font-size: 0.68rem;
  text-transform: uppercase;
  letter-spacing: 0.06em;
  color: {theme.accent};
  font-weight: 700;
}}
.lir-anchor-prompt {{ font-size: 0.9rem; }}

/* -- review badges -------------------------------------------------------- */

.lir-review-badge {{
  display: inline-block;
  font-size: 0.66rem;
  font-weight: 700;
  letter-spacing: 0.04em;
  color: {theme.card_background};
  padding: 2px 8px;
  border-radius: 999px;
}}
{_review_rules(theme)}

/* -- inline links -------------------------------------------------------- */

.lir-link {{
  border-bottom: 1px dotted {theme.accent};
  cursor: help;
}}

/* -- learning path overview page ------------------------------------------ */

.lir-path-page .lir-path-card {{
  display: flex;
  gap: 14px;
  align-items: flex-start;
}}
.lir-path-steps {{
  display: flex;
  flex-direction: column;
  gap: 14px;
}}
.lir-path-index {{
  font-family: {theme.code_font};
  font-weight: 700;
  color: {theme.accent};
  min-width: 2ch;
}}
.lir-path-optional {{
  font-size: 0.72rem;
  color: {theme.ink_muted};
  border: 1px solid {theme.card_border};
  border-radius: 999px;
  padding: 1px 8px;
  margin-left: 6px;
}}

@media print {{
  body.lir-page {{ background: #fff; }}
  .lir-card {{ box-shadow: none; break-inside: avoid; }}
}}
""".strip()
