# Architecture Notes: Knowledge Materialization

## Where this sits

`handbook.materialize` sits between `SyncState.known_items()` (a
vault's `Problem`s) and everything downstream of a graph -- the graph
builder, the compiler, and now `handbook.sync.notebook_site`. It does
not replace or wrap any of them; it produces more items of the kind
they already know how to consume.

```
Problems (SyncState)
    -> MaterializationEngine.materialize()
    -> Algorithm / Pattern / Mistake / Contest KnowledgeItems
    -> written to the vault (Handbook.store), same as any hand-authored note
    -> fed into the *same* GraphBuilder / KnowledgeCompiler everything else uses
```

## The problem this solves

`Problem.algorithms`, `.patterns`, and `.mistakes` are lists of
`Relation`, and a `Relation.target` is just a string. Before this
chunk, if no `Algorithm` note existed for "Binary Search",
`graph.resolver.Resolver` didn't fail -- it fabricated a *shadow node*
so the edge could still resolve. Shadow nodes are graph-only. Nothing
is ever compiled or rendered for one, because nothing was ever
persisted for it. In a freshly-synced vault (sync only ever produces
`Problem` items -- see `docs/DEVELOPER_NOTES_SYNC.md`), that meant
*every* algorithm, pattern, and mistake a person's problems referenced
had no page, nowhere to aggregate "which problems used this", nowhere
to write down the actual intuition. `MaterializationEngine` is what
gives them one.

## Key decisions and why

**Never fabricate content, only structure.** A materialized item's
free-text fields (`intuition`, `implementation`, `pitfalls`, `cause`,
`prevention`, `description`, ...) are left at their defaults.
`notes` carries one mechanical sentence recording provenance -- how
many problems referenced it, when -- not invented domain knowledge.
`docs/ARCHITECTURE_NOTES_COMPILER.md` already drew this line for the
compiler ("a sparse `KnowledgeItem` compiles to a correspondingly
sparse `Page` -- never padded, never guessed"); this chunk draws it in
the same place, one layer up, for the exact reason
`docs/DEVELOPER_NOTES_SYNC.md` originally gave for not doing this at
all: "creating real Algorithm notes automatically from tag names would
be guessing at content this prototype has no business guessing at."
The guessing is still out of bounds. What's not a guess is a title, a
kind, and real backlinks to the problems that already reference it --
those are facts already sitting in the vault, just not yet given a
page.

**Create once, ever.** A slug is materialized at most one time per
vault. Once `MaterializeState` has a record of it, this engine never
re-renders or re-writes its file again. There is still no vault
loader (see `docs/DEVELOPER_NOTES_SYNC.md`), so nothing in this
codebase can currently tell a freshly-materialized stub apart from one
a person has since filled in with real intuition and pitfalls by hand.
Re-rendering from this engine's own (necessarily blank) in-memory copy
and overwriting the file would silently erase that prose. Rather than
build a fragile field-by-field merge with no way to detect what
changed, this chunk takes the same tradeoff already accepted for
Problem hand-edits -- "invisible until a real vault loader exists" --
and applies it uniformly to materialized items. A materialized item's
*backlinks* stay fresh regardless, because those are computed live
from the graph at compile/dashboard time
(`handbook.learning.compiler.helpers.related_pairs`,
`handbook.sync.notebook_site._backlinks`), never stored on the item
itself.

**A hand-authored note always wins.** If a person has already created
`Algorithms/binary-search.md` themselves (their own id) before the
engine ever sees a `Problem` referencing "Binary Search", persisting
the engine's own shell would collide at that path with a different id
-- `Handbook.store()` raises `DuplicateItemError` rather than silently
overwriting a different item at the same slug. The engine catches
this, records a warning, and skips that item for the run (it isn't
added to the materialized set, since its real id/content aren't
knowable without a vault loader). Materialization degrades gracefully
here rather than crashing the whole sync run over one collision.

**Deterministic ids, not random ones.** A materialized item's id is
`uuid5(NAMESPACE, "{kind}:{slug}")`. Materializing the same slug twice
-- two separate runs, or two engines pointed at the same vault -- must
converge on one id, never collide, for the same reason
`handbook.learning.compiler.helpers.stable_id` derives compiled-page
ids deterministically one layer up.

**Kind inference is frequency-based, with a fixed tie-break.** A slug
can legitimately be referenced under more than one field across
different problems (tagged as an algorithm on one, a pattern on
another -- inconsistent tagging happens). Whichever field referenced
it most often wins; ties break `algorithms > patterns > mistakes`.
Either way a warning is recorded, not hidden, so a person can notice
and go fix the tagging by hand.

**Contests are handled separately, and only get real backlinks once.**
`Problem.contest_id`/`.contest` are plain strings, not `Relation`s --
`GraphBuilder` never creates an edge for them (it only reflects on
`Relation`-typed fields; see `handbook.graph.builder`). So unlike
Algorithm/Pattern/Mistake, a materialized `Contest`'s `problems` field
is populated directly, once, at creation time, by scanning every
`Problem` sharing that `contest_id` -- using each `Problem`'s own `id`
as the `Relation` target (not its title), so it resolves to the exact
node, not a slug guess. Combined with "create once, ever" above, this
means a `Contest`'s problem list is a snapshot as of the run that
first synced any problem from it; a person upsolving more problems
from the same contest in a later sync run won't retroactively appear
on that Contest's page without a vault loader to safely merge new
relations into hand-editable content. Documented here, not hidden --
same as every other simplification in this codebase.

## What this is not

This is not a second graph resolver, a duplicate detector, or a vault
loader. It reuses `Handbook.store()` for persistence,
`handbook.utils.slug.note_slug()` for the exact same slug rule
`Resolver` already uses, and produces plain `KnowledgeItem` instances
that flow through the *unmodified* `GraphBuilder` and
`KnowledgeCompiler` like any other item. Nothing about the compiler,
the LIR, or the knowledge models changed to support this.

## Performance notes

Materializing 240 synthetic Problems (each referencing 0-2 algorithms
and up to 1 mistake, ~15 distinct algorithm/mistake names, 48 distinct
contests) into 68 new items took ~150ms on a single core, including
every `Handbook.store()` file write. A second run over the same 240
Problems (nothing new to materialize) is dominated entirely by
`MaterializeState` reconstructing 68 items from JSON -- a few
milliseconds. Materialization scales with distinct referenced
slugs, not with problem count, so this stays cheap even as a vault's
Problem count grows; what grows linearly is the one-time file-write
cost the first time each new algorithm/pattern/mistake/contest is
seen.

## Testing

- `tests/test_materialize_state.py` -- `MaterializeState` in isolation:
  round-tripping through JSON, `known_items()` reconstruction.
- `tests/test_materialize_engine.py` -- the engine in isolation:
  dedup across casing, stable ids across runs, no-fabrication
  guarantee, ambiguous-field warnings, hand-authored-note protection,
  Contest backlink correctness.
- `tests/test_sync_materialization_integration.py` -- through
  `run_sync()`: a synced Problem's CF tags and contest id actually
  produce materialized notes on disk, re-running sync doesn't
  duplicate them, and -- the thing this chunk was most at risk of
  breaking -- `report.notebook_pages` (the pre-existing,
  separately-tested `compile_notebook_pages()` contract) is completely
  unaffected.
