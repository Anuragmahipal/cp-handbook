"""The sync pipeline: Codeforces submission -> vault -> graph -> revision note.

Every stage below calls straight into the *existing* engine
(:meth:`~handbook.handbook.Handbook.store`,
:class:`~handbook.graph.GraphBuilder`,
:func:`handbook.template_engine.render` via
:mod:`handbook.sync.note_writer`) rather than reimplementing any of it.
This module's only job is orchestration and deduplication:

.. code-block:: text

    Submission (Codeforces)
        -> Problem object          (handbook.sync.mapping)
        -> Knowledge object        (models.Problem, a KnowledgeItem)
        -> Store                   (Handbook.store)
        -> Graph update            (GraphBuilder, over every known Problem)
        -> Revision note           (handbook.sync.revision_note / note_writer)
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from handbook.evolution import EvolutionLog, EvolutionReport, LearningEvolutionEngine
from handbook.exceptions import DuplicateItemError
from handbook.graph import DuplicateReport, GraphBuilder, KnowledgeGraph
from handbook.handbook import Handbook
from handbook.materialize import MaterializationEngine, MaterializationReport, MaterializeState
from handbook.models import Problem
from handbook.sync.codeforces import CFSubmission, CodeforcesClient
from handbook.sync.mapping import build_problem_item
from handbook.sync.notebook import CompiledNotebookPage, compile_notebook_pages
from handbook.sync.notebook_site import NotebookSiteReport, build_notebook_site
from handbook.sync.note_writer import WrittenNote, write_revision_note
from handbook.sync.revision_note import RevisionNote, generate_revision_note
from handbook.sync.state import SyncState
from handbook.utils.filesystem import atomic_write

_GRAPH_EXPORT_RELATIVE_PATH = Path(".handbook") / "graph.json"


@dataclass(frozen=True, slots=True)
class SyncedProblem:
    """One newly-imported problem: everything the CLI needs to report on it."""

    item: Problem
    vault_path: Path
    note: RevisionNote
    note_paths: WrittenNote


@dataclass(frozen=True, slots=True)
class SyncReport:
    """Everything ``cp-handbook sync`` needs to print a summary."""

    handle: str
    fetched_submissions: int
    newly_accepted: int
    imported: list[SyncedProblem] = field(default_factory=list)
    already_known: int = 0
    total_known_problems: int = 0
    graph_node_count: int = 0
    graph_edge_count: int = 0
    duplicate_report: DuplicateReport | None = None
    notebook_pages: list[CompiledNotebookPage] = field(default_factory=list)
    """Every notebook page (re)compiled this run -- see
    :mod:`handbook.sync.notebook`. Populated for the *full* cumulative
    set of known items, not just this run's newly imported ones, the
    same "rebuild from everything known" convention already used for
    :attr:`graph_node_count`/:attr:`graph_edge_count` above."""
    materialization: MaterializationReport | None = None
    """What :class:`~handbook.materialize.engine.MaterializationEngine`
    did this run -- which Algorithms/Patterns/Mistakes/Contests were
    newly given a page of their own vs. already known, and any
    warnings (ambiguous kinds, skipped hand-authored collisions). See
    :mod:`handbook.materialize`."""
    notebook_site: NotebookSiteReport | None = None
    """The connected notebook site built this run -- every compiled
    page plus the ``Notebook/index.html`` dashboard, with real
    cross-page links and shared navigation. See
    :mod:`handbook.sync.notebook_site`. Built over Problems *and*
    whatever :attr:`materialization` produced, so it is a strict
    superset of :attr:`notebook_pages` -- the latter is kept around
    unchanged as this chunk's own building block and contract, not
    replaced by it."""
    evolution: EvolutionReport | None = None
    """What :class:`~handbook.evolution.engine.LearningEvolutionEngine`
    recorded this run -- new Problem-solved events, knowledge-growth
    milestones, and mastery-status changes. See :mod:`handbook.evolution`.
    Empty (not ``None``) on a run that imported nothing new and whose
    materialized items' backlink counts/mastery didn't change --
    ``EvolutionReport.is_empty`` distinguishes "ran and found nothing
    new" from "never ran"."""


def run_sync(
    handle: str,
    *,
    vault_root: Path,
    client: CodeforcesClient,
    count: int = 10_000,
) -> SyncReport:
    """Run one full sync of ``handle``'s accepted submissions into ``vault_root``.

    Safe to call repeatedly: a submission id already recorded in this
    vault's :class:`~handbook.sync.state.SyncState` is never
    reprocessed, and a Codeforces problem that already has a Problem
    note in this vault never gets a second one, even if the handle
    solved it again (e.g. resubmitted in another language).
    """
    state = SyncState(vault_root)
    handbook = Handbook(root=vault_root)

    submissions = client.fetch_submissions(handle, count=count)

    by_problem_key: dict[str, list[CFSubmission]] = defaultdict(list)
    for submission in submissions:
        by_problem_key[submission.problem.problem_key].append(submission)

    accepted = [s for s in submissions if s.accepted]
    new_accepted = sorted(
        (s for s in accepted if not state.has_imported(s.id)),
        key=lambda s: s.creation_time,
    )

    imported: list[SyncedProblem] = []
    for submission in new_accepted:
        problem_key = submission.problem.problem_key
        state.mark_imported(submission.id)

        if state.has_problem(problem_key):
            # This Codeforces problem already has a note in this vault
            # (e.g. the handle re-solved it in a different language).
            # The submission id is still marked imported above so it's
            # never re-examined, but no second note is created.
            continue

        prior_wrong = [
            s
            for s in by_problem_key[problem_key]
            if s.creation_time < submission.creation_time
            and s.verdict not in (None, "OK")
        ]

        item = build_problem_item(submission, prior_wrong_attempts=len(prior_wrong))
        vault_path, item = _store_with_title_collision_handling(
            handbook, item, problem_key
        )

        note = generate_revision_note(item, submission, prior_wrong)
        note_paths = write_revision_note(vault_root, note)

        state.remember_problem(problem_key, item)
        imported.append(
            SyncedProblem(
                item=item, vault_path=vault_path, note=note, note_paths=note_paths
            )
        )

    graph = GraphBuilder(state.known_items()).build()
    _export_graph(vault_root, graph)
    notebook_pages = compile_notebook_pages(vault_root, state.known_items(), graph)

    materialize_state = MaterializeState(vault_root)
    materialization = MaterializationEngine(handbook, materialize_state).materialize(
        state.known_items()
    )
    materialize_state.save()

    # A second, separate graph -- Problems *and* whatever was just
    # materialized -- so every Problem.algorithms/patterns/mistakes/
    # contest_id relation now resolves to a real node instead of a
    # graph-only shadow (see `handbook.materialize`). Kept separate
    # from `graph` above on purpose: `graph_node_count`/`graph_edge_count`
    # /`duplicate_report` describe the vault's authored Problems alone,
    # unaffected by what this run happened to materialize.
    site_items = list(state.known_items()) + materialization.all_items
    site_graph = GraphBuilder(site_items).build()

    evolution_log = EvolutionLog(vault_root)
    evolution = LearningEvolutionEngine(evolution_log).evolve(site_items, site_graph)

    notebook_site = build_notebook_site(vault_root, site_items, site_graph, evolution=evolution_log)

    state.handle = handle
    state.last_synced_at = datetime.now()
    state.save()

    return SyncReport(
        handle=handle,
        fetched_submissions=len(submissions),
        newly_accepted=len(new_accepted),
        imported=imported,
        already_known=len(new_accepted) - len(imported),
        total_known_problems=state.problem_count(),
        graph_node_count=len(graph),
        graph_edge_count=len(graph.edges()),
        duplicate_report=graph.duplicate_detector().find_duplicates(),
        notebook_pages=notebook_pages,
        materialization=materialization,
        notebook_site=notebook_site,
        evolution=evolution,
    )


def _store_with_title_collision_handling(
    handbook: Handbook, item: Problem, problem_key: str
) -> tuple[Path, Problem]:
    """Store ``item``, disambiguating its title if a *different* problem
    already occupies that title's slot.

    Codeforces problem titles are not globally unique -- two different
    contests can each have a problem called "Sum" or "Array". The
    common case (a genuinely new title) stores exactly as-is; only a
    real collision pays the cost of a rename, using ``problem_key``
    (globally unique by construction) to guarantee the retry succeeds.
    """
    try:
        return handbook.store(item), item
    except DuplicateItemError:
        disambiguated = item.model_copy(
            update={"title": f"{item.title} (CF {problem_key})"}
        )
        return handbook.store(disambiguated), disambiguated


def _export_graph(vault_root: Path, graph: KnowledgeGraph) -> None:
    """Persist the rebuilt graph as JSON alongside the vault's other
    ``.handbook`` bookkeeping, so ``cp-handbook status`` (or any future
    tool) can inspect graph structure without rebuilding it itself.
    """
    atomic_write(vault_root / _GRAPH_EXPORT_RELATIVE_PATH, graph.export_json())
