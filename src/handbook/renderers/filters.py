"""Reusable rendering helpers shared by every Markdown template.

These are plain, dependency-free string functions -- no model or storage
imports -- registered as Jinja filters in :mod:`handbook.template_engine`.
Keeping them here (rather than inline in template code) is what makes
them genuinely reusable: every template calls the *same* function for
the same job, so a callout, a relationship diagram, or a status emoji
looks identical everywhere instead of drifting template-by-template.

Nothing in this module touches the filesystem or the storage layer --
rendering stays a pure "data in, Markdown string out" concern.
"""

from __future__ import annotations

from datetime import datetime

# -- Obsidian callout construction -------------------------------------------


def blockquote(text: str) -> str:
    """Prefix every line of *text* with Markdown blockquote syntax.

    Used via ``{% filter blockquote %}...{% endfilter %}`` to turn any
    block of rendered Markdown -- including the ``[!type]`` header line
    itself -- into a valid Obsidian callout. Every line inside a callout
    must start with ``>``, blank lines included, or the callout ends
    early and the rest silently falls back to plain paragraph text.

    Keeps a single trailing newline, matching how built-in Jinja
    filters (e.g. ``upper``) behave -- template source relies on that
    to get a real blank line between two adjacent callouts.
    """
    lines = text.strip("\n").splitlines()
    quoted = "\n".join(f"> {line}".rstrip() if line.strip() else ">" for line in lines)
    return quoted + "\n"


def editable_block(value: str, marker: str, placeholder: str) -> str:
    """Wrap free-form, human/AI-authored prose in HTML comment markers.

    Structured fields (tags, relations, timestamps) are always fully
    regenerated from the model on every render -- that's fine, they're
    deterministic. Prose fields (an algorithm's intuition, a mistake's
    cause) are meant to accumulate hand-written insight over time, so
    they're marked as a distinct island in the output:

    ``<!-- ai:<marker>:start -->`` / ``<!-- ai:<marker>:end -->``

    Storage doesn't do read-merge-write yet (that's future work, not
    this chunk), but the markers make each editable region unambiguous
    to find and are invisible in Obsidian's rendered preview.
    """
    stripped = value.strip() if value else ""
    body = stripped if stripped else placeholder
    return f"<!-- ai:{marker}:start -->\n{body}\n<!-- ai:{marker}:end -->"


# -- Mermaid ------------------------------------------------------------------


def mermaid_escape(text: str) -> str:
    """Escape characters that would break a quoted Mermaid node label."""
    return text.replace('"', "&quot;").replace("\n", " ").strip()


# -- Small value-to-display transforms -----------------------------------------

_STATUS_EMOJI = {
    "Active": "🟢",
    "Learning": "🌱",
    "Needs Review": "🔁",
    "Mastered": "⭐",
    "Archived": "📦",
}

_DIFFICULTY_EMOJI = {
    "Trivial": "⚪",
    "Easy": "🟢",
    "Medium": "🟡",
    "Hard": "🟠",
    "Very Hard": "🔴",
    "Expert": "⚫",
}

_PLATFORM_EMOJI = {
    "Codeforces": "🟦",
    "LeetCode": "🟧",
    "AtCoder": "⬜",
    "CodeChef": "🟫",
    "CSES": "🟩",
    "ICPC": "🏅",
    "IOI": "🏅",
    "HackerRank": "🟩",
    "SPOJ": "🟪",
    "USACO": "🐄",
    "TopCoder": "🟨",
    "Other": "🔹",
}


def status_emoji(status: str) -> str:
    return _STATUS_EMOJI.get(status, "🔹")


def difficulty_emoji(difficulty: str | None) -> str:
    return _DIFFICULTY_EMOJI.get(difficulty or "", "")


def platform_emoji(platform: str) -> str:
    return _PLATFORM_EMOJI.get(platform, "🔹")


def format_dt(value: str) -> str:
    """Render an ISO-8601 timestamp as a short, human-friendly date."""
    try:
        return datetime.fromisoformat(value).strftime("%b %d, %Y")
    except (TypeError, ValueError):
        return value


def format_minutes(value: int | None) -> str:
    """Render a minute count as e.g. ``1h 35m`` / ``45m``."""
    if value is None:
        return "—"
    hours, minutes = divmod(value, 60)
    if hours and minutes:
        return f"{hours}h {minutes}m"
    if hours:
        return f"{hours}h"
    return f"{minutes}m"
