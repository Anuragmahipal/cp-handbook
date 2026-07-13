# Knowledge → LIR Compiler — Architecture Notes

## Where this sits

```
Algorithm / Problem / Pattern / Mistake / Contest   (handbook.models, Chunk 2)
        │
        │  KnowledgeCompiler(graph).compile(item)
        ▼
CompilerRegistry.compiler_for(item)  ──►  one Compiler subclass per kind
        │                                  (Algorithm/Problem/Pattern/
        │                                   Mistake/Contest Compiler)
        ▼
handbook.learning.compiler.helpers    (stable ids, timestamps, graph-driven
        │                              "Related X" sections, default anchors)
        │
        ├─ reads  handbook.graph.KnowledgeGraph   (built once, over every
        │          known item, by GraphBuilder — untouched by this chunk)
        │
        ▼
Page (handbook.learning, untouched by this chunk)
        │
        ▼
NotebookRenderer().render(page)   (untouched by this chunk)
        │
        ▼
Vault/Notebook/<Kind>/<slug>.html
```

`handbook.sync.notebook.compile_notebook_pages()` is the one piece of
CLI wiring: after `cp-handbook sync` rebuilds the graph over every
known item (as it already did before this chunk), it now also compiles
and renders every item the registry supports, writing each page next
to — never inside — the existing Markdown note folders. Everything
this package touches (`handbook.models`, `handbook.graph`,
`handbook.learning`, `handbook.renderers.notebook`) is read, not
modified; the only files outside `handbook.learning.compiler/` this
chunk edits are `handbook/sync/notebook.py` (new),
`handbook/sync/pipeline.py` and `handbook/sync/cli.py` (both a few
lines each, to call it).

## Key decisions and why

**Every id is `uuid5`-derived from `(item.id, qualifier)`, never
`uuid4()`.** Every LIR `Identified` defaults to a random id unless a
caller passes one — correct for hand-authored content, wrong for a
compiler, where recompiling the same note on every `cp-handbook sync`
run should produce byte-identical output rather than a fresh object
graph each time. `stable_id()` fixes this once, centrally, so no
concrete compiler has to think about it. The same reasoning applies to
timestamps: `Page`/`Section` copy `item.created_at`/`updated_at`
instead of stamping `datetime.now()`.

**Relation filtering keys off `Edge.provenance`, not `Edge.type`.**
Several unrelated fields share a default `RelationType` (`Problem.
algorithms` and `Problem.patterns` are both `USES`), and a few field
*names* are reused across classes entirely (`Mistake.
related_algorithms` and `Pattern.related_algorithms`). `GraphBuilder`
already stamps every edge with `provenance=f"field:{field_name}"` —
using that as the discriminator (see `helpers._edge_matches`) means
this package asks the graph a precise question ("just this field")
without inventing a second relation taxonomy of its own. This is what
"consume the graph, don't duplicate its logic" means concretely.

**A compiled `Page`'s section headings are named after what's
mechanically true, not after the hand-authored example fixtures'
taxonomy.** `examples/algorithm_page.json` splits an algorithm's
content into "Recognition" and "Core Idea" — two paragraphs of
authored prose that don't correspond to two separate domain-model
fields (`Algorithm` has one `intuition` string). Rather than
fabricating that split, `AlgorithmCompiler` produces a single
"Intuition" section. Every compiler follows the same rule: a section
exists exactly when a real field backs it, named for that field's
actual content. See `tests/test_compiler_examples_comparison.py` for
where this is checked directly against the fixtures.

**A `MemoryAnchor` is built before the `Section` it lives in, never
patched on after.** `Section` validates that every anchor's `target_id`
resolves to its own id or one of its blocks' at construction time (and
every LIR model is frozen), so `Section.model_copy()` — which does not
re-validate — is never used to retrofit an anchor. `helpers.
section_with_anchor()`/`sections_with_optional_anchor()` compute the
section's id and the anchor's target together, then construct the
`Section` once, fully formed.

**Default anchors follow one "best available content" priority per
kind**, via `helpers.pick_anchor()`: Algorithm prefers Implementation
over Intuition over Pitfalls; Pattern prefers Recognition Cues over
Intuition; Mistake prefers Prevention over Root Cause over What
Happened (which always exists); Contest prefers Takeaways over
Overview (which always exists). Every anchor's prompt is a short,
deterministic template string — never AI-generated, per the chunk
brief — and every `ReviewCue` starts at its own defaults (`NEW`,
`strength=0.0`, no review history), which needed no overriding at all.

**Two authored fields describing the same relationship from opposite
ends are merged, not shown twice.** An algorithm's own
`related_problems` and a problem's own `algorithms` both mean "this
problem uses this algorithm." `helpers.merge_pairs()` dedupes by the
far node's id so a reader sees one "Related Problems" list, not two
overlapping ones.

**No content is synthesized that isn't backed by a real field.** No
`DiagramBlock` is generated from bare metadata (Algorithm/Pattern carry
no diagram field at all — inventing one would mean fabricating a
visual that isn't in the source knowledge). `ProblemCompiler` never
invents a "Statement"/"Approach"/"Code" section: `Problem` has no field
for any of the three (that's `RevisionNote`'s job, filled in by a
human). A sparse `KnowledgeItem` compiles to a correspondingly sparse
`Page` — never padded, never guessed — with `CompilationResult.
warnings` naming exactly which sections were skipped and why.

**`Topic` is explicitly out of scope.** It wasn't in the chunk's
`IMPLEMENT` list, and compiling one is a different shape of problem —
aggregating its children's content rather than projecting its own
fields. `CompilerRegistry` raises `UnsupportedKnowledgeTypeError` for
it (and for any other future unregistered type) rather than guessing.

**Recompiling every known item's notebook page on every sync run does
not conflict with `ARCHITECTURE.md`'s "never regenerate entire
notebooks" principle.** That principle is about knowledge: sync never
re-derives or overwrites an existing `Problem`'s content, and this
chunk never touches a hand-edited Markdown note. What gets rebuilt
every run is the *rendered* `.html` view — already declared disposable
by `ARCHITECTURE.md`'s own "renderers are disposable" — and rebuilding
a disposable, deterministic view from unchanged knowledge is
idempotent by construction (see the determinism decision above), not a
regeneration of anything a person authored.

## Performance notes

Compiling one item is O(edges touching that item), not O(total graph
edges): every "Related X" section calls `KnowledgeGraph.related()`
once per authored field, and that method reads only the adjacency
lists for the one node in question. Compiling every item in a vault is
therefore linear in the graph's total edge count, the same complexity
class `GraphBuilder.build()` itself already has.

Measured on a synthetic vault of 240 interrelated items (40
algorithms, 20 patterns, 30 mistakes, 150 problems; 430 edges after
`GraphBuilder`) on the container this chunk was built in:

| Stage                                   | Total    | Per item   |
|------------------------------------------|---------:|-----------:|
| `GraphBuilder(items).build()`             | ~11 ms   | —          |
| `KnowledgeCompiler(graph).compile_all()`  | ~129 ms  | ~0.54 ms   |
| `NotebookRenderer().render()` (all pages) | ~14 ms   | ~0.06 ms   |

Compilation dominates render cost, mostly from per-block/-section
`uuid5` hashing and Pydantic construction/validation — both fixed,
small costs per object, not per-edge. `tests/test_compiler_large_vault.
py` asserts a generous 10-second ceiling for the same workload as a
regression guard against an accidental quadratic blowup, not as a
tight perf benchmark.

The one thing worth remembering operationally: build the
`KnowledgeGraph` once and hand it to a single `KnowledgeCompiler`,
reused across every item (exactly what `handbook.sync.notebook.
compile_notebook_pages()` does) — constructing a fresh graph per item
would turn a linear pipeline into a quadratic one for no benefit.

## Testing

- **Per-compiler** (`test_compiler_algorithm/problem/pattern/mistake/
  contest.py`): every section's presence/absence follows its backing
  field, in isolation from the other four compilers.
- **Determinism** (`test_compiler_determinism.py`): idempotency (same
  object, compiled twice) and cross-object determinism (two separately
  constructed, content-identical items compile identically).
- **Round-trip** (`test_compiler_round_trip.py`): every compiled `Page`
  survives `dump_page`/`load_page`, for populated and sparse items
  alike, across all five kinds.
- **Graph integration** (`test_compiler_graph_integration.py`): link
  targets resolve to real (including shadow) node ids; a five-item web
  of relations compiles correctly from *every* item's point of view,
  not just the one under direct test; prerequisites reflect one
  authored hop, not a transitively-walked chain.
- **Large-vault** (`test_compiler_large_vault.py`): 240 items, all
  compile, all round-trip, no dangling link targets, within a generous
  time bound.
- **Example comparison** (`test_compiler_examples_comparison.py`): the
  "Example LIR vs Compiled LIR" quality check the brief asked for —
  see the "section headings" decision above.
- **Sync/CLI integration** (`test_sync_notebook_compilation.py`): the
  Definition of Done, exercised end-to-end — `run_sync`/`cp-handbook
  sync` produce real `.html` files with no second command, are
  idempotent across repeated runs, and one file per synced problem.

## What's explicitly deferred

- **`Topic` compilation.** A different shape of problem (aggregating
  children, not projecting fields) — see "Key decisions" above.
- **`LearningPath` generation.** The chunk's `IMPLEMENT` list is five
  per-kind compilers plus the registry/context/result/facade — no
  `LearningPath` builder. Composing a suggested study order across many
  compiled pages from `PREREQUISITE` edges is a natural next chunk, for
  the same reason `ARCHITECTURE_NOTES_LEARNING.md` already deferred a
  `LearningPath` ↔ `Page` consistency check: it's an artifact that
  spans many pages, not a property of compiling one item.
- **Diagrams synthesized from metadata.** No `DiagramBlock` is ever
  generated by a compiler in this chunk — only ones a human explicitly
  authored (via a future richer domain field) would appear. See "Key
  decisions" above for why fabricating one here would cross the "Do
  NOT use AI" line in spirit even without literally calling a model.
- **Spaced-repetition scheduling.** `ReviewCue`s start at their own
  defaults (`NEW`, `strength=0`); nothing here updates them after a
  review — that's `handbook.learning.review`'s documented future work,
  unaffected by this chunk.
- **A richer `Problem.notes`/solution-code field.** `ProblemCompiler`
  cannot produce "Statement"/"Approach"/"Code" sections because
  `Problem` has no field for any of the three today; adding one (and
  deciding whether it belongs on the domain model or stays exclusively
  in `RevisionNote`) is a domain-model decision outside this chunk.
