"""CSS-only syntax highlighting.

No JavaScript runs in the browser to color code -- all the work
happens here, at render time, producing static ``<span class="tok-...">``
markup that a stylesheet colors via plain CSS class selectors. This is
a small, practical regex tokenizer for a handful of common languages,
not a general lexer: good enough to make CP code readable, not a
replacement for a real compiler front end. An unrecognized language
still renders correctly -- just without color, via the ``_GENERIC``
fallback below.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from html import escape


@dataclass(frozen=True, slots=True)
class _LanguageSyntax:
    keywords: frozenset[str]
    line_comment: str | None
    block_comment: tuple[str, str] | None
    preprocessor_prefix: str | None
    """A line-start prefix (e.g. ``"#"`` in C/C++) whose whole line is
    styled as a preprocessor directive rather than tokenized further."""


_CPP_KEYWORDS = frozenset(
    """
    alignas alignof and and_eq asm auto bitand bitor bool break case
    catch char char8_t char16_t char32_t class compl concept const
    consteval constexpr constinit const_cast continue co_await
    co_return co_yield decltype default delete do double dynamic_cast
    else enum explicit export extern false float for friend goto if
    inline int long mutable namespace new noexcept not not_eq nullptr
    operator or or_eq private protected public register
    reinterpret_cast requires return short signed sizeof static
    static_assert static_cast struct switch template this thread_local
    throw true try typedef typeid typename union unsigned using
    virtual void volatile wchar_t while xor xor_eq
    """.split()
)

_PYTHON_KEYWORDS = frozenset(
    """
    False None True and as assert async await break class continue
    def del elif else except finally for from global if import in is
    lambda nonlocal not or pass raise return try while with yield
    match case
    """.split()
)

_JAVA_KEYWORDS = frozenset(
    """
    abstract assert boolean break byte case catch char class const
    continue default do double else enum extends final finally float
    for goto if implements import instanceof int interface long native
    new package private protected public return short static strictfp
    super switch synchronized this throw throws transient try void
    volatile while var record sealed permits yield
    """.split()
)

_LANGUAGES: dict[str, _LanguageSyntax] = {
    "cpp": _LanguageSyntax(_CPP_KEYWORDS, "//", ("/*", "*/"), "#"),
    "c": _LanguageSyntax(_CPP_KEYWORDS, "//", ("/*", "*/"), "#"),
    "java": _LanguageSyntax(_JAVA_KEYWORDS, "//", ("/*", "*/"), None),
    "javascript": _LanguageSyntax(_JAVA_KEYWORDS, "//", ("/*", "*/"), None),
    "python": _LanguageSyntax(_PYTHON_KEYWORDS, "#", None, None),
}

_GENERIC = _LanguageSyntax(frozenset(), "//", ("/*", "*/"), None)
"""Used for any language not in ``_LANGUAGES``: still highlights
strings/numbers/comments using the most common conventions, just with
no keyword list to color."""

_TOKEN_PATTERN = re.compile(
    r"""
    (?P<block_comment>/\*.*?\*/)
  | (?P<line_comment>//[^\n]*|\#[^\n]*)
  | (?P<string>"(?:\\.|[^"\\])*"|'(?:\\.|[^'\\])*')
  | (?P<number>\b\d+\.?\d*[fFlLuU]*\b)
  | (?P<identifier>[A-Za-z_]\w*)
    """,
    re.VERBOSE | re.DOTALL,
)


def _resolve_language(language: str) -> _LanguageSyntax:
    return _LANGUAGES.get(language.strip().lower(), _GENERIC)


def highlight_line(source_line: str, language: str) -> str:
    """Return ``source_line`` as HTML: escaped, with recognized tokens
    wrapped in ``<span class="tok-KIND">``.

    Operates one line at a time (block comments spanning multiple
    lines are treated as a line comment on each line they touch,
    rather than tracked as multi-line state) -- ``CodeBlock`` is
    rendered one table row per line for line numbers and per-line
    annotations, so a tokenizer that carries state across lines would
    need to thread that state through the caller too. For the block
    comment styles CP code actually uses (docblocks, banner comments),
    per-line comment detection reads correctly in practice.
    """
    syntax = _resolve_language(language)

    if syntax.preprocessor_prefix and source_line.lstrip().startswith(
        syntax.preprocessor_prefix
    ):
        return f'<span class="tok-pre">{escape(source_line)}</span>'

    pieces: list[str] = []
    cursor = 0
    for match in _TOKEN_PATTERN.finditer(source_line):
        if match.start() > cursor:
            pieces.append(escape(source_line[cursor : match.start()]))
        pieces.append(_render_token(match, syntax))
        cursor = match.end()
    pieces.append(escape(source_line[cursor:]))
    return "".join(pieces)


def _render_token(match: re.Match[str], syntax: _LanguageSyntax) -> str:
    kind = match.lastgroup
    text = match.group()

    if kind == "identifier":
        if text in syntax.keywords:
            return f'<span class="tok-kw">{escape(text)}</span>'
        return escape(text)

    css_class = {
        "block_comment": "tok-com",
        "line_comment": "tok-com",
        "string": "tok-str",
        "number": "tok-num",
    }.get(kind)
    if css_class is None:  # pragma: no cover - defensive, all groups covered above
        return escape(text)
    return f'<span class="{css_class}">{escape(text)}</span>'
