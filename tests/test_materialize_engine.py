"""Tests for handbook.materialize.engine.MaterializationEngine."""

from __future__ import annotations

from pathlib import Path

from handbook.handbook import Handbook
from handbook.materialize import MaterializationEngine, MaterializeState
from handbook.models import Algorithm, Platform, Problem, Relation


def _problem(title: str, **fields) -> Problem:
    """A minimal valid Problem. Note that ``contest`` is a required,
    non-blank field on the real model (see ``handbook.models.problem``)
    -- so every Problem, real or in these tests, always belongs to
    *some* contest, and the Materialization Engine will always produce
    a Contest for it unless that contest was already materialized.
    Tests that only care about Algorithm/Pattern/Mistake materialization
    filter the report down by ``.item.KIND`` rather than asserting on
    ``report.created`` as a whole, to keep that (correct, intentional)
    behavior from making unrelated assertions brittle.
    """
    fields.setdefault("platform", Platform.CODEFORCES)
    fields.setdefault("contest", "1868")
    fields.setdefault("index", "A")
    return Problem(title=title, **fields)


def _created_by_kind(report, kind: str):
    return [m for m in report.created if m.item.KIND == kind]


def _engine(vault_root: Path) -> tuple[MaterializationEngine, MaterializeState, Handbook]:
    handbook = Handbook(root=vault_root)
    state = MaterializeState(vault_root)
    return MaterializationEngine(handbook, state), state, handbook


def test_materializes_an_algorithm_from_a_problem_reference(vault_root: Path):
    problem = _problem("Candies", algorithms=[Relation(target="Binary Search")])
    engine, state, _ = _engine(vault_root)

    report = engine.materialize([problem])

    algorithms = _created_by_kind(report, "algorithm")
    assert len(algorithms) == 1
    materialized = algorithms[0]
    assert materialized.item.title == "Binary Search"
    assert materialized.item.KIND == "algorithm"
    assert materialized.is_new is True
    assert materialized.reference_count == 1
    assert (vault_root / "Algorithms" / "binary-search.md").exists()


def test_materializes_patterns_mistakes_and_contests_too(vault_root: Path):
    problem = _problem(
        "Candies",
        contest_id="1868",
        patterns=[Relation(target="Two Pointers")],
        mistakes=[Relation(target="Off By One")],
    )
    engine, state, _ = _engine(vault_root)

    report = engine.materialize([problem])

    kinds_created = {m.item.KIND for m in report.created}
    assert kinds_created == {"pattern", "mistake", "contest"}
    assert (vault_root / "Patterns" / "two-pointers.md").exists()
    assert (vault_root / "Mistakes" / "off-by-one.md").exists()
    assert (vault_root / "Contests" / "1868.md").exists()


def test_same_slug_from_different_casing_deduplicates(vault_root: Path):
    p1 = _problem("Candies", algorithms=[Relation(target="Binary Search")])
    p2 = _problem("Ropes", algorithms=[Relation(target="binary search")])
    engine, state, _ = _engine(vault_root)

    report = engine.materialize([p1, p2])

    algorithms = [m for m in report.created if m.item.KIND == "algorithm"]
    assert len(algorithms) == 1
    assert algorithms[0].reference_count == 2
    # first-seen casing wins as the canonical title
    assert algorithms[0].item.title == "Binary Search"


def test_never_creates_duplicates_and_ids_are_stable_across_runs(vault_root: Path):
    problem = _problem("Candies", algorithms=[Relation(target="Binary Search")])
    engine1, state1, handbook = _engine(vault_root)
    report1 = engine1.materialize([problem])
    state1.save()
    first_id = _created_by_kind(report1, "algorithm")[0].item.id

    # A second engine, backed by a fresh MaterializeState re-loaded from disk
    state2 = MaterializeState(vault_root)
    engine2 = MaterializationEngine(handbook, state2)
    report2 = engine2.materialize([problem])

    assert report2.created == []
    already_known_algorithm = [
        m for m in report2.already_known if m.item.KIND == "algorithm"
    ][0]
    assert already_known_algorithm.item.id == first_id
    assert already_known_algorithm.is_new is False

    # No second file was written, no duplicate on disk
    assert list((vault_root / "Algorithms").glob("*.md")) == [
        vault_root / "Algorithms" / "binary-search.md"
    ]


def test_materialized_items_carry_no_fabricated_prose(vault_root: Path):
    problem = _problem("Candies", algorithms=[Relation(target="Binary Search")])
    engine, state, _ = _engine(vault_root)

    report = engine.materialize([problem])

    algorithm = _created_by_kind(report, "algorithm")[0].item
    assert isinstance(algorithm, Algorithm)
    assert algorithm.intuition == ""
    assert algorithm.implementation == ""
    assert algorithm.pitfalls == []
    # provenance is recorded honestly, not as invented domain content
    assert "Auto-materialized" in algorithm.notes
    assert "1 referencing problem" in algorithm.notes


def test_ambiguous_field_across_problems_produces_a_warning_not_a_crash(vault_root: Path):
    p1 = _problem("A", algorithms=[Relation(target="Two Pointers")])
    p2 = _problem("B", patterns=[Relation(target="Two Pointers")])
    p3 = _problem("C", patterns=[Relation(target="Two Pointers")])
    engine, state, _ = _engine(vault_root)

    report = engine.materialize([p1, p2, p3])

    # 2 references as a pattern beats 1 as an algorithm
    patterns = _created_by_kind(report, "pattern")
    algorithms = _created_by_kind(report, "algorithm")
    assert len(patterns) == 1
    assert len(algorithms) == 0
    assert any("Two Pointers" in w for w in report.warnings)


def test_hand_authored_note_is_never_overwritten(vault_root: Path):
    engine, state, handbook = _engine(vault_root)
    handbook.store(Algorithm(title="Binary Search", intuition="my own hand-written notes"))
    before = (vault_root / "Algorithms" / "binary-search.md").read_text()

    problem = _problem("Candies", algorithms=[Relation(target="Binary Search")])
    report = engine.materialize([problem])

    after = (vault_root / "Algorithms" / "binary-search.md").read_text()
    assert after == before
    assert _created_by_kind(report, "algorithm") == []
    assert "Binary Search" in report.skipped
    assert any("already exists" in w for w in report.warnings)


def test_contest_links_to_the_real_problems_that_belong_to_it(vault_root: Path):
    p1 = _problem("Candies", contest_id="1868")
    p2 = _problem("Ropes", contest_id="1868")
    engine, state, _ = _engine(vault_root)

    report = engine.materialize([p1, p2])

    contests = [m for m in report.created if m.item.KIND == "contest"]
    assert len(contests) == 1
    contest = contests[0].item
    linked_ids = {relation.target for relation in contest.problems}
    assert linked_ids == {p1.id, p2.id}


def test_bare_problem_only_materializes_its_contest(vault_root: Path):
    # `contest` is a required field on Problem, so a Contest is always
    # materialized -- but with no algorithms/patterns/mistakes tagged,
    # nothing else should be.
    problem = _problem("Bare Problem")
    engine, state, _ = _engine(vault_root)

    report = engine.materialize([problem])

    assert not report.is_empty()
    kinds = {m.item.KIND for m in report.created}
    assert kinds == {"contest"}
    assert report.warnings == []
