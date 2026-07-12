"""Tests for handbook.renderers.notebook.syntax."""

from __future__ import annotations

from handbook.renderers.notebook.syntax import highlight_line


def test_cpp_keyword_is_wrapped():
    html = highlight_line("int x = 1;", "cpp")
    assert '<span class="tok-kw">int</span>' in html


def test_cpp_line_comment_is_wrapped():
    html = highlight_line("// a comment", "cpp")
    assert '<span class="tok-com">// a comment</span>' in html


def test_python_keyword_is_wrapped():
    html = highlight_line("if x == 1:", "python")
    assert '<span class="tok-kw">if</span>' in html


def test_python_comment_uses_hash():
    html = highlight_line("# note", "python")
    assert '<span class="tok-com"># note</span>' in html


def test_cpp_preprocessor_line_is_wrapped_whole():
    html = highlight_line("#include <vector>", "cpp")
    assert html == '<span class="tok-pre">#include &lt;vector&gt;</span>'


def test_python_hash_is_not_treated_as_preprocessor():
    # Python has no preprocessor concept -- '#' there is always a comment.
    html = highlight_line("#!/usr/bin/env python", "python")
    assert '<span class="tok-com">' in html
    assert "tok-pre" not in html


def test_string_literal_is_wrapped():
    html = highlight_line('string s = "hello";', "cpp")
    assert '<span class="tok-str">&quot;hello&quot;</span>' in html


def test_number_literal_is_wrapped():
    html = highlight_line("int x = 42;", "cpp")
    assert '<span class="tok-num">42</span>' in html


def test_html_is_always_escaped():
    html = highlight_line('cout << a < b << ">";', "cpp")
    assert "<" not in html.replace("<span", "\x00").replace("</span>", "\x00")


def test_unknown_language_still_escapes_without_keywords():
    html = highlight_line("let x = <y>;", "rust")
    assert "tok-kw" not in html
    assert "&lt;y&gt;" in html


def test_identifier_that_is_not_a_keyword_is_left_unwrapped():
    html = highlight_line("myVariable", "cpp")
    assert html == "myVariable"
