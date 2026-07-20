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
from handbook.models import Contest, Problem, Submission
from handbook.sync.codeforces import CFSubmission, CodeforcesClient
from handbook.sync.mapping import build_contest_item, build_problem_item, build_submission
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
    materialization: MaterializationReport | None = None
    notebook_site: NotebookSiteReport | None = None
    evolution: EvolutionReport | None = None


def run_sync(
    handle: str,
    *,
    vault_root: Path,
    client: CodeforcesClient,
    count: int = 10_000,
) -> SyncReport:
    """Run one full sync of ``handle``'s submissions into ``vault_root``.

    Safe to call repeatedly: a submission id already recorded in this
    vault's :class:`~handbook.sync.state.SyncState` is never
    reprocessed, and a Codeforces problem that already has a Problem
    note in this vault never gets a second one, even if the handle
    solved it again (e.g. resubmitted in another language).

    All submissions -- accepted or not -- are stored in the sync state
    as historical records. Accepted submissions trigger Problem note
    creation. Unsolved problems (submissions but no AC) also become
    Problem items with ``solved=False``. Contest metadata is fetched
    from ``contest.list`` and stored as ``Contest`` items.
    """
    state = SyncState(vault_root)
    handbook = Handbook(root=vault_root)

    submissions = client.fetch_submissions(handle, count=count)

    # Fetch contest metadata for all contests referenced in submissions
    contest_ids = {
        s.contest_id for s in submissions
        if s.contest_id is not None
    }
    contests_by_id: dict[int, Contest] = {}
    if contest_ids:
        try:
            all_contests = client.fetch_contests(gym=True)
            for cf_contest in all_contests:
                if cf_contest.id in contest_ids:
                    contest = build_contest_item(cf_contest)
                    contests_by_id[cf_contest.id] = contest
                    # Store contest in handbook (idempotent)
                    try:
                        handbook.store(contest)
                    except DuplicateItemError:
                        pass
        except Exception:
            # Best-effort: if contest.list fails, continue without contests
            pass

    # Group ALL submissions by problem key, chronologically
    by_problem_key: dict[str, list[CFSubmission]] = defaultdict(list)
    for submission in submissions:
        by_problem_key[submission.problem.problem_key].append(submission)
    for key in by_problem_key:
        by_problem_key[key].sort(key=lambda s: s.creation_time)

    # Identify newly-accepted submissions BEFORE we store anything
    accepted = [s for s in submissions if s.accepted]
    new_accepted = sorted(
        (s for s in accepted if not state.has_imported(s.id)),
        key=lambda s: s.creation_time,
    )

    # Store every new submission in state (accepted or not)
    for submission in submissions:
        if not state.has_imported(submission.id):
            sub = build_submission(submission)
            state.store_submission(sub)

    imported: list[SyncedProblem] = []

    # Process accepted submissions -> Problem notes
    for submission in new_accepted:
        problem_key = submission.problem.problem_key

        if state.has_problem(problem_key):
            continue

        all_cf_subs = by_problem_key[problem_key]
        submission_history = [build_submission(s) for s in all_cf_subs]

        item = build_problem_item(submission, submission_history=submission_history)
        vault_path, item = _store_with_title_collision_handling(
            handbook, item, problem_key
        )

        note = generate_revision_note(item, submission, submission_history)
        note_paths = write_revision_note(vault_root, note)

        state.remember_problem(problem_key, item)
        imported.append(
            SyncedProblem(
                item=item, vault_path=vault_path, note=note, note_paths=note_paths
            )
        )

    # Process unsolved problems (submissions exist but no AC)
    for problem_key, cf_subs in by_problem_key.items():
        if state.has_problem(problem_key):
            continue
        if any(s.accepted for s in cf_subs):
            continue  # Already handled above

        # Build an unsolved Problem item
        submission_history = [build_submission(s) for s in cf_subs]
        # Use the latest submission as the "trigger" for building
        latest_sub = max(cf_subs, key=lambda s: s.creation_time_seconds)
        item = build_problem_item(latest_sub, submission_history=submission_history)
        vault_path, item = _store_with_title_collision_handling(
            handbook, item, problem_key
        )

        # No revision note for unsolved problems (no AC to learn from)
        state.remember_problem(problem_key, item)

    graph = GraphBuilder(state.known_items()).build()
    _export_graph(vault_root, graph)
    notebook_pages = compile_notebook_pages(vault_root, state.known_items(), graph)

    materialize_state = MaterializeState(vault_root)
    materialization = MaterializationEngine(handbook, materialize_state).materialize(
        state.known_items()
    )
    materialize_state.save()

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
