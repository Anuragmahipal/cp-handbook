"""Tests for CompilerRegistry / default_registry / KnowledgeCompiler dispatch."""

from __future__ import annotations

import pytest

from handbook.graph import GraphBuilder
from handbook.learning.compiler import (
    AlgorithmCompiler,
    CompilerRegistry,
    ContestCompiler,
    KnowledgeCompiler,
    MistakeCompiler,
    PatternCompiler,
    ProblemCompiler,
    UnsupportedKnowledgeTypeError,
    default_registry,
)
from handbook.learning.compiler.context import CompilationContext
from handbook.models import Algorithm, Contest, Mistake, Pattern, Platform, Problem, Topic


def _context() -> CompilationContext:
    return CompilationContext(graph=GraphBuilder([]).build())


def test_default_registry_covers_every_implemented_kind():
    registry = default_registry()
    context = _context()

    assert isinstance(
        registry.compiler_for(Algorithm(title="A")), AlgorithmCompiler
    )
    assert isinstance(
        registry.compiler_for(
            Problem(title="P", platform=Platform.CODEFORCES, contest="1", index="A")
        ),
        ProblemCompiler,
    )
    assert isinstance(registry.compiler_for(Pattern(title="Pat")), PatternCompiler)
    assert isinstance(registry.compiler_for(Mistake(title="M")), MistakeCompiler)
    assert isinstance(
        registry.compiler_for(Contest(title="C", platform=Platform.CODEFORCES)),
        ContestCompiler,
    )
    # exercised via .compile() too, not just resolution:
    result = registry.compile(Algorithm(title="A"), context)
    assert result.page.metadata.title == "A"


def test_topic_is_explicitly_unsupported():
    registry = default_registry()
    with pytest.raises(UnsupportedKnowledgeTypeError):
        registry.compiler_for(Topic(title="Graph Theory"))


def test_registry_resolves_subclasses_via_mro():
    class SpecialAlgorithm(Algorithm):
        pass

    registry = default_registry()
    compiler = registry.compiler_for(SpecialAlgorithm(title="A"))
    assert isinstance(compiler, AlgorithmCompiler)


def test_register_overrides_existing_compiler():
    registry = CompilerRegistry()
    registry.register(Algorithm, AlgorithmCompiler())
    custom = AlgorithmCompiler()
    registry.register(Algorithm, custom)
    assert registry.compiler_for(Algorithm(title="A")) is custom


def test_unregistered_type_raises_with_a_clear_message():
    registry = CompilerRegistry()
    with pytest.raises(UnsupportedKnowledgeTypeError, match="Topic"):
        registry.compiler_for(Topic(title="X"))


def test_knowledge_compiler_uses_default_registry_when_none_given():
    graph = GraphBuilder([]).build()
    compiler = KnowledgeCompiler(graph)
    result = compiler.compile(Algorithm(title="Binary Search"))
    assert result.page.metadata.title == "Binary Search"


def test_knowledge_compiler_compile_all_preserves_order():
    algo = Algorithm(title="A")
    pattern = Pattern(title="B")
    graph = GraphBuilder([algo, pattern]).build()
    compiler = KnowledgeCompiler(graph)

    results = compiler.compile_all([algo, pattern])

    assert [r.page.metadata.title for r in results] == ["A", "B"]


def test_knowledge_compiler_propagates_unsupported_type():
    graph = GraphBuilder([]).build()
    compiler = KnowledgeCompiler(graph)
    with pytest.raises(UnsupportedKnowledgeTypeError):
        compiler.compile(Topic(title="Graph Theory"))
