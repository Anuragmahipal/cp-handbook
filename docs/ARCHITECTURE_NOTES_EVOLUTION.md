# Architecture Notes: Learning Evolution

## Where this sits

`handbook.evolution` sits downstream of everything else, touching
nothing it depends on:

```
Problems (SyncState) + materialized items (MaterializationEngine)
    -> GraphBuilder                          (unchanged, reused)
    -> LearningEvolutionEngine.evolve()       -> EvolutionLog (append-only)
    -> KnowledgeCompiler(evolution=log)       (optional field, unchanged otherwise)
    -> build_notebook_site(evolution=log)     (optional field, unchanged otherwise)
```

Every integration point is an *optional* parameter with a default that
reproduces prior behavior exactly: `CompilationContext.evolution`,
`CompilationContext.items_by_id`, `KnowledgeCompiler(..., evolution=,
items_by_id=)`, `build_notebook_site(..., evolution=)`. Nothing in
`Sync`, `Storage`, `Graph`, `LIR`, `Renderer`, or `Notebook Site` was
redesigned -- see "Why everything is an optional field" below for why
that was possible without contorting any of them.

## The problem this solves

Before this chunk, the notebook was a photograph, not a history. Every
`cp-handbook sync` recompiled every page from the vault's *current*
state -- correct, but memoryless. A person's 50th solve using Binary
Search produced the same "Related Problems: 50 items" a script could
compute from nothing at all; there was no record of *when* mastery
happened, no way to ask "what did I learn this month" that didn't
require re-deriving it from scratch, and nothing that couldn't be
recomputed identically from a single snapshot of the vault. Part 6's
"the notebook should become richer every week without losing previous
knowledge" needed something a snapshot fundamentally can't provide:
a fact, once true, stays recorded even after the vault that produced
it moves on.

## Key decisions and why

**History lives in its own file, not on the `KnowledgeItem`s
themselves.** The obvious alternative -- store a `history: list[...]`
field directly on `Algorithm`/`Problem` -- was rejected because it
would mean rewriting a person's Markdown note's frontmatter on every
single sync run purely to append one line, which is exactly the
clobbering risk `handbook.materialize` was built to avoid (see its own
architecture notes: no vault loader exists, so re-rendering a
`KnowledgeItem` model back to disk can't distinguish machine-owned
data from a person's hand-written prose). Keeping history in
`EvolutionLog`, entirely separate from the vault's authored notes,
means every `KnowledgeItem` file is exactly as append-safe/hand-edit-
safe after this chunk as it was before it.

**JSON Lines, appended, never rewritten.** `EvolutionLog.append()`
opens its file in `"a"` mode and writes one line. There is no code
path anywhere in this module that reads the file back in and writes it
out again in full. "Running sync twice must never destroy history"
(Part 6's own words) is therefore not just an invariant this module
tries to maintain -- there is no operation available to it that
*could* destroy a previously-written line, short of someone deleting
the file by hand outside this codebase entirely.

**Idempotency without a diff.** There's no stored "what the vault
looked like last time" to compare against. Instead, every fact this
engine might record gets a *deterministic* id
(`uuid5(NAMESPACE, "solved:{problem_id}")`,
`uuid5(NAMESPACE, "growth:{item_id}:{new_total}")`,
`uuid5(NAMESPACE, "mastery:{item_id}:{status}")`) derived from what the
fact actually says. `LearningEvolutionEngine.evolve()` can therefore
just *try* to record every fact that's true right now, on every
single run, and let `EvolutionLog.append()`'s own duplicate-id check
silently discard whatever hasn't changed. This is what makes "duplicate
sync" (Part 7) a non-event rather than a special case the engine has
to detect -- it's the same code path as a completely new run, just one
where nothing happens to be new.

**Growth and mastery are milestones, not per-occurrence events.**
Syncing 150 problems that all use Binary Search in one run produces
*one* `KnowledgeGrowth` event ("now used by 150 problems"), not 150.
The event id is derived from the achieved total
(`growth:{item_id}:150`), so it's really recording "the count reached
150", which is a single fact true at a single moment -- not "this
individual problem was the Nth use", which would be 150 separate,
much less useful facts. Same reasoning for `MasteryChange`: solving 5
problems with the same algorithm in one sync run crosses every
threshold at once, and only the *final* status reached gets recorded
(see `test_large_sync_records_an_event_per_problem_and_growth_for_
shared_algorithms`) -- a person cares that they reached "mastered",
not that they technically passed through "learning" and "due" in the
same afternoon.

**The mastery formula is a fixed threshold table, not a scoring
model.** `mastery_for_count()`: 0 solves -> `NEW`, 1-2 -> `LEARNING`,
3-4 -> `DUE`, 5+ -> `MASTERED`, reusing
`handbook.learning.enums.ReviewStatus` (the same enum `ReviewCue`
already carries) rather than inventing a second mastery vocabulary.
This is monotonic in solve count alone -- **no recency decay, no
"forgetting."** That's a real, deliberately accepted limitation, not
an oversight: a decaying estimate needs a notion of "now", and this
module already anchors everything else to the vault's own latest
activity rather than wall-clock time (see next point) specifically to
stay deterministic and testable; bolting a wall-clock decay onto just
the mastery formula would break that consistency for one field. A
fixed, published threshold table is also something a person can
actually predict and disagree with -- "5 solves means mastered" is
checkable; a hidden decay curve is not. A proper spaced-repetition
scheduler is real, future, additive work (see What's explicitly
deferred), not a redesign of this one.

**Anchored to the vault's own latest activity, not `datetime.now()`.**
`solve_frequency_per_week`, `learning_velocity_per_two_weeks`,
`weekly_solves`, `monthly_solves`, and the solve-streak calculations
all measure "recent" relative to the latest solve *in the data*, not
real wall-clock time. Two consequences, both intentional: these
statistics are fully deterministic and testable without freezing time
in every test, and they stay meaningful for a person who doesn't sync
every single day -- "0 solves this week" would be a permanent,
uninformative false alarm for anyone who practices in weekend bursts
if "this week" meant the actual calendar week regardless of when they
last opened the notebook.

**Why everything is an optional field, not a new required argument.**
`CompilationContext` gained two fields (`evolution`, `items_by_id`),
both defaulting to `None`/`{}`. `KnowledgeCompiler` gained two matching
constructor keyword arguments. `build_notebook_site` gained one. Every
one of these defaults exactly reproduces the function's behavior from
before this chunk existed -- which is what let every golden-snapshot
test, every examples-comparison test, and all 599 pre-existing tests
pass completely unmodified (see Testing below): none of them pass the
new arguments, so none of them see any different behavior. An optional
field with a safe default is the smallest change that can add a
capability without touching an existing contract -- the same technique
`handbook.materialize`'s chunk used when it first added
`CompilationContext.evolution`... except it didn't; this is the chunk
that introduced `CompilationContext` gaining any evolution-shaped
field at all. The technique itself, though, is exactly the one
`handbook.materialize` and `handbook.sync.notebook_site` already
established for their own optional additions (`SyncReport.
materialization`, `SyncReport.notebook_site`, `build_notebook_site`'s
own earlier optional-nothing-yet signature) -- this chunk just applies
it one more time.

**Why `items_by_id` had to be added at all.** `AlgorithmCompiler`'s
new sections (rating histogram, recent activity, difficulty
progression) need each backlinked `Problem`'s own `rating` and
`created_at`. `KnowledgeGraph`'s `Node` objects deliberately carry
none of that (see `handbook.graph.node` -- a `Node` is just
`id`/`kind`/`title`, on purpose, to keep the graph a lightweight
relationship index rather than a second copy of every item's data).
Rather than have `handbook.evolution.stats` reach back into storage to
re-load a `Problem` by id (coupling it to `Handbook`/`StorageEngine`
for no good reason), the caller that already has every item in memory
(`build_notebook_site`, and this chunk's own tests) just hands the
lookup dict along.

**Evolution-derived sections live in two different layers, on
purpose.** Part 2's algorithm-specific stats (Learning Progress,
Rating Histogram, Recent Activity) are built as `Section`s inside
`AlgorithmCompiler`, using the existing LIR block types
(`DiagramBlock`/`VisualBlock` for the histogram -- the first compiler
in this codebase to use `DiagramBlock`, and exactly the generic
"visual data" case it exists for). Part 4's chronological history
(`Learning History`) is a *shared* helper
(`handbook.learning.compiler.helpers.learning_history_section`),
called from all five compilers identically, because it needs nothing
kind-specific -- an `EvolutionLog` entry is already keyed by plain
`item_id`. Part 3's vault-wide Personal Statistics, by contrast, isn't
built in the compiler at all -- there's no single `KnowledgeItem` that
represents "the whole vault" for a `Section` to attach to -- so it's a
new dashboard card in `handbook.sync.notebook_site`, the same layer
that already owns every other vault-wide dashboard statistic (Weak
Areas, Most Used Algorithms, ...).

## What's explicitly deferred

- **Recency-decaying mastery / real spaced-repetition scheduling.**
  `ReviewCue`'s own docstring already names this as a "future review-
  scheduling engine"; this chunk's fixed threshold table is a
  deliberately simple placeholder in the same spirit, not a first
  draft of that engine.
- **Per-item-scoped Personal Statistics** (e.g. "my rating growth just
  on Binary Search problems"). Today's `Personal Statistics` card is
  vault-wide; per-item slicing would need `stats.py`'s functions
  parameterized by a problem subset, which is a natural, additive
  next step, not a redesign of anything here.
- **A vault loader that lets `EvolutionLog` reconcile against
  hand-edited `KnowledgeItem` notes.** Not needed by this chunk --
  `EvolutionLog` never reads or writes a `KnowledgeItem`'s own file at
  all -- but would still unlock reconciling a person's own
  hand-corrections (e.g. manually marking a problem `solved=False`
  after the fact) against already-recorded history.

## Performance notes

240 synthetic Problems (mirroring `handbook.materialize`'s and
`handbook.sync.notebook_site`'s own benchmark data), each referencing
0-2 of 15 algorithm names: `LearningEvolutionEngine.evolve()` recorded
240 solved events, 20 knowledge-growth milestones, and 20 mastery
changes in ~10ms. A full `build_notebook_site(..., evolution=log)`
pass (308 pages, now including every evolution-derived section) stayed
in the same low-hundreds-of-milliseconds range as
`handbook.sync.notebook_site`'s own non-evolution benchmark. A second
run over the same 240 problems recorded zero new events, confirming
the idempotency guarantee holds at this scale, not just in the small
hand-built test fixtures above.

## Testing

Organized to mirror this chunk's own Part 7 checklist by name:

- **Duplicate sync** --
  `test_evolution_engine.py::test_duplicate_sync_does_not_duplicate_history`,
  `test_sync_evolution_integration.py::test_running_sync_twice_on_the_same_data_does_not_duplicate_history`.
- **Incremental sync** --
  `test_evolution_engine.py::test_incremental_sync_appends_only_the_new_events`,
  `test_sync_evolution_integration.py::test_incremental_sync_appends_new_history_without_touching_old`.
- **History consistency** --
  `test_evolution_engine.py::test_history_consistency_across_many_incremental_syncs`
  (ten sequential incremental syncs; verifies nothing already recorded
  is ever lost).
- **Large syncs** --
  `test_evolution_engine.py::test_large_sync_records_an_event_per_problem_and_growth_for_shared_algorithms`
  (150 problems in one run).
- **Mastery updates** --
  `test_evolution_engine.py::test_mastery_updates_incrementally_as_solves_accumulate`,
  `test_evolution_engine.py::test_mastery_for_count_thresholds`.
- **Timeline ordering** --
  `test_evolution_log.py::test_timeline_entries_are_sorted_chronologically`,
  `test_evolution_engine.py::test_timeline_ordering_reflects_when_things_actually_happened`,
  `test_evolution_engine.py::test_per_item_timeline_ordering_mixes_solves_growth_and_mastery_correctly`.

Plus: `test_evolution_events.py`/`test_evolution_log.py` for the data
model and append-only log in isolation; `test_evolution_stats.py` for
every deterministic formula (histogram bucketing, velocity window,
rating growth, solve streaks) against hand-computed expected values;
`test_compiler_algorithm_evolution.py` for the compiler-layer
sections, including an explicit regression test that compiling with no
evolution log reproduces the exact pre-evolution behavior every
golden-snapshot test depends on; `test_sync_evolution_integration.py`
for the full `run_sync()` path. All 599 pre-existing tests
(materialization, notebook site, compiler golden snapshots, sync
pipeline) pass completely unmodified.
