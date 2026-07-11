# CP Handbook

A structured, file-based knowledge base for competitive programming —
Algorithms, Problems, Patterns, and Mistakes — stored as plain Markdown
in a local vault, with a small Python library sitting in front of it.

This README documents the **persistence engine**, the **knowledge model
layer**, and the **Beautiful Note System**: the foundation every future
feature (Search, MCP, AI workflows) will be built on top of.

## Install

```bash
uv sync
```

Requires Python 3.12+.

## Quick start

```python
from handbook import Handbook
from handbook.models import Algorithm

hb = Handbook()

hb.store(
    Algorithm(
        title="Binary Exponentiation"
    )
)
```

No configuration is required to try this out: if `config/settings.toml`
has no `vault.path` set, the vault defaults to `./vault` in the current
directory. For real usage, set `vault.path` in `config/settings.toml`,
or pass a root explicitly:

```python
hb = Handbook(root="/path/to/my/vault")
```

## The generic `store()` API

Every knowledge type is persisted the same way — the caller never
supplies a folder, filename, or template:

```python
from handbook.models import Algorithm, Problem, Pattern, Mistake, Contest, Topic

hb.store(Algorithm(title="Binary Exponentiation"))
hb.store(Problem(title="Two Sum", platform="LeetCode", contest="Easy", index="1"))
hb.store(Pattern(title="Sliding Window"))
hb.store(Mistake(title="Off-by-one in binary search"))
hb.store(Contest(title="Educational Round 100", platform="Codeforces"))
hb.store(Topic(title="Graph Theory"))
```

`Handbook.create_algorithm(title, **fields)` still exists as a thin
convenience wrapper, but it now just calls `store(Algorithm(...))`
internally — there is no separate file-writing path for algorithms.

## Knowledge model layer

Every model inherits `KnowledgeItem`, which carries the metadata that's
meaningful for *any* CP knowledge object:

* **identity** — `id`, `title`, `aliases`, and a computed `slug`
  (the same canonical, filesystem-safe identifier storage uses for
  filenames — derived once, not recomputed independently elsewhere).
* **classification** — `tags`, `difficulty` (`Difficulty` enum),
  `status` (`KnowledgeStatus` enum).
* **provenance** — `sources`, `references`.
* **relationships** — `prerequisites` and `related_items`: lists of
  first-class `Relation(target, type, note)` objects, not free-form
  Markdown links. Every type-specific relationship field (`Problem.algorithms`,
  `Pattern.related_algorithms`, `Contest.problems`, ...) is `list[Relation]`
  too, using the same `RelationType` vocabulary (`prerequisite`, `uses`,
  `appears_in`, `contains`, ...). Plain strings are also accepted as
  shorthand — `algorithms=["Binary Search"]` becomes
  `[Relation(target="Binary Search", type=RelationType.USES)]` automatically.
* **free text** — `notes`.
* **timestamps** — `created_at`, `updated_at`.

Six concrete types build on this: `Algorithm`, `Problem`, `Pattern`,
`Mistake`, `Contest`, `Topic` — see `src/handbook/models/*.py` for each
type's own fields. Enums live in `models/enums.py` and are lenient:
`Platform("cf")` and `Platform("Codeforces")` both resolve to
`Platform.CODEFORCES`, so callers (human or AI) don't need to know the
exact canonical spelling, but every stored object still ends up with one
canonical, typed value rather than a free-form string.

```python
lca = Algorithm(title="LCA", prerequisites=["Binary Lifting"])
hld = Algorithm(title="Heavy-Light Decomposition", prerequisites=["LCA"])
```

`lca.prerequisites[0]` is `Relation(target="Binary Lifting", type=RelationType.PREREQUISITE)`
— a typed edge a future graph/search layer can walk directly, not a
Markdown `[[Binary Lifting]]` link to be parsed later.

## Beautiful Note System

`Algorithm`, `Problem`, `Pattern`, `Mistake`, and `Contest` render as
production-quality Obsidian notes, not flat field dumps. (`Topic` keeps
its plain Chunk 2 template — it's outside this pass's scope.) Every
note follows the same visual hierarchy:

```
# <emoji> Title

> [!tip]+ Quick Facts             <- always expanded, scalar metadata at a glance
> [!abstract]+ <Primary prose>    <- the main editable write-up, expanded by default
> [!example]- <Supplementary>     <- collapsed: code, full lists -- progressive disclosure
> [!example]- 🗺️ Relationships     <- collapsed: bullet list + Mermaid graph (only if non-empty)
> [!info]- 🔎 Live Cross-References (Dataview)   <- collapsed Dataview query
> [!quote]- 📚 Sources & References              <- collapsed, only if present
---
> [!info]- 📋 Metadata             <- shared footer: id / slug / kind / created / updated
```

* **Callouts + collapsible sections** — every section is an Obsidian
  callout (`> [!type]`); supplementary ones default collapsed (`]-`),
  primary content defaults expanded (`]+`), giving progressive
  disclosure without hiding anything.
* **Mermaid** — a `prerequisites`/`related_*` relation list becomes a
  `graph LR` diagram (e.g. `LCA -->|prerequisite| "Heavy-Light
  Decomposition"`), generated straight from the item's own `Relation`
  data. Only rendered when there's at least one relation; skipped
  otherwise rather than showing an empty graph.
* **Dataview** — each type emits a fenced `dataview` query block (e.g.
  "Problems that use this algorithm", "Other mistakes in the same
  category"). These are plain query *text* resolved by Obsidian's
  Dataview plugin at view time — the handbook itself does no querying,
  indexing, or search.
* **AI-managed sections** — free-form prose fields (an algorithm's
  `intuition`, a mistake's `cause`) are wrapped in
  `<!-- ai:<field>:start/end -->` HTML-comment markers: invisible in
  Obsidian's reading view, and a clear, greppable boundary around
  hand-written content that's meant to persist and accumulate, as
  opposed to the structured/generated sections around it (frontmatter,
  relationship lists, the metadata footer) which are safe to fully
  regenerate on every render. Storage doesn't yet do read-merge-write
  on top of these markers — that's future work, not this chunk's — but
  the scaffolding is there.
* **Reusable rendering helpers** — `handbook/renderers/filters.py`
  (blockquote formatting, Mermaid label escaping, status/difficulty/
  platform emoji, date/duration formatting) is registered once as Jinja
  filters in `template_engine.py` and used by every template, so a
  callout or a date looks identical everywhere instead of drifting
  template-by-template.
* **Template inheritance** — every dedicated template extends
  `templates/_shared/layout.md.j2` for the one piece that's genuinely
  identical everywhere (the closing metadata callout); `templates/_shared/macros.j2`
  holds the reusable Jinja macros (`relation_list`, `relationship_diagram`,
  `metadata_footer`). Frontmatter and body stay per-type, since forcing a
  single shared shape onto genuinely different fields would hurt
  readability more than it'd save.

Rendering stays independent from storage: nothing above changes what
`Handbook.store()`, `StorageEngine`, or the public `Renderer`/
`MarkdownRenderer` API look like from the outside.

## Architecture

```
Handbook.store(item)
        │
        ├─ resolve_folder(item)         core/folders.py   -> "Algorithms" / "Problems" / ...
        ├─ storage.plan(item, ...)      core/storage.py   -> where it goes + resolved metadata
        ├─ renderer.render(plan.item)   renderers/*.py    -> the actual file content (opaque string)
        └─ storage.commit(plan, content)                  -> atomic write + index update
```

* **`core/folders.py`** — the single registry mapping a knowledge type to
  its vault subfolder. Adding a new type is one new entry here.
* **`core/renderer.py`** — an abstract `Renderer` interface
  (`render(item) -> str`, plus an `extension`). `MarkdownRenderer` is the
  only implementation today; HTML/JSON/PDF renderers can be added later
  without touching storage at all.
* **`core/storage.py`** — `StorageEngine` is the only code that touches
  the filesystem. It never looks inside the `content` string it's asked
  to write — it just decides *where* content goes and *whether* a write
  is allowed, then writes it atomically. See "Duplicate policy" below.
* **`core/index.py`** — a small JSON index (`<vault>/.handbook/index.json`)
  that lets storage answer "have I seen this id before?" and "is this
  filename taken?" in O(1), without parsing any rendered file. This is
  what keeps storage format-agnostic.

## Duplicate policy

Checked in this order, every time `store()` is called:

1. **Same `id` (UUID) as something already in the vault → same object.**
   Treated as an update: the file is rewritten, `created_at` is
   preserved from the first time this id was stored, `updated_at` is
   refreshed to now. If the title changed (and so the filename would
   change), the item is relocated and its old file is removed.
2. **Same title/slug as an existing item, but a different id → collision.**
   * `overwrite=False` (default): rejected with `DuplicateItemError`,
     nothing is written.
   * `overwrite=True`: the existing file is fully replaced.
3. **Neither → a brand new item is written.**

## Folder layout

```
Algorithm -> Algorithms/
Problem   -> Problems/
Pattern   -> Patterns/
Mistake   -> Mistakes/
Contest   -> Contests/
Topic     -> Topics/
```

## Knowledge Graph

The handbook is no longer just a collection of rendered Markdown files
— `handbook.graph` builds an in-memory **Knowledge Graph** on top of the
knowledge model layer: the canonical runtime representation of every
relationship, used by search, duplicate detection, and any future
feature that needs to walk the vault's structure without re-parsing
Markdown.

The graph is a **derived index** — the vault remains the source of
truth. Nothing in this layer touches the filesystem; `GraphBuilder`
takes a list of already-parsed `KnowledgeItem` objects (however they got
loaded) and produces a `KnowledgeGraph`:

```python
from handbook.graph import GraphBuilder

graph = GraphBuilder(items).build()

graph.get("Binary Lifting")                    # by id, slug, alias, or title
graph.related("Two Sum")                        # every edge touching a node
graph.backlinks("Segment Tree")                  # computed from edges, never from Markdown
graph.reachable(problem.id)                      # everything reachable in the graph
graph.shortest_path(a.id, b.id)
graph.topological_sort()                         # raises GraphCycleError if not a DAG

graph.search_engine().search("segment tree")
graph.duplicate_detector().find_duplicates()

graph.export_json()
graph.export_dot()
graph.export_networkx()                          # nx.node_link_graph(...)-compatible dict
```

* **`graph/node.py`, `graph/edge.py`** — `Node` is a lightweight
  projection of a `KnowledgeItem`'s identity/classification metadata
  (never its rendered body). `Edge` is a typed, directed connection
  derived from a `Relation`, carrying confidence, provenance, and a
  `derived` flag for edges the graph invents itself later. Multiple
  edges between the same pair of nodes are supported.
* **`graph/index.py`** — `GraphIndex` is the single in-memory store of
  nodes/edges and every lookup index (id, slug, alias, title, tag, kind,
  status, adjacency) built on top of them. Every other class below reads
  from one `GraphIndex` rather than keeping its own copy of the data.
* **`graph/resolver.py`** — `Resolver` turns a raw `Relation.target`
  string into a node: id → slug → alias → title, in that order, falling
  back to a deterministic **shadow node** for anything unresolved, so a
  dangling reference stays queryable instead of disappearing.
* **`graph/builder.py`** — `GraphBuilder` discovers every
  `list[Relation]` field on an item *generically*, via its Pydantic
  schema, rather than hardcoding `Problem.algorithms`,
  `Contest.problems`, etc. one by one — a new knowledge type can add a
  new relation field without this class ever changing. `update()`
  supports incremental rebuilds: recomputing just the edges sourced by
  the items that changed.
* **`graph/traversal.py`** — `Traversal` is pure, read-only graph
  algorithms (`neighbors`, `reachable`, `shortest_path`,
  `topological_sort`, `cycle_detection`, `subgraph`, ...), kept
  deliberately separate from construction. `topological_sort` and
  `cycle_detection` only consider `FORWARD` edges — a `BIDIRECTIONAL`
  edge (`similar_to`, `related`) describes a symmetric relationship, not
  a hierarchy, and would make any pair it connects trivially cyclic.
* **`graph/search.py`** — `SearchEngine` ranks title/alias/tag/metadata
  matches (exact → prefix → substring → fuzzy), plus dedicated
  `prefix()` and `by_relation()` (relation-type queries) methods.
* **`graph/duplicates.py`** — `DuplicateDetector` finds duplicate
  titles, duplicate aliases, near-duplicate names (string similarity),
  and duplicate edges. `extra_detectors` is the seam a future semantic/
  embeddings-based detector plugs into without this class changing.
* **`graph/export.py`** — `Exporter` serializes to JSON, Graphviz DOT,
  and a NetworkX-compatible node-link structure, independent of every
  algorithm above it.
* **`graph/graph.py`** — `KnowledgeGraph` composes all of the above into
  one convenient facade.



## Codeforces Sync

This is the project's first end-to-end usable workflow: solve a problem
on Codeforces, and get a stored knowledge-base entry plus a revision
note out the other end, with zero manual note-taking.

```bash
uv run cp-handbook init    # configure your Codeforces handle + vault location
uv run cp-handbook sync    # fetch newly accepted submissions, update the vault
uv run cp-handbook status  # see what's configured and what's been synced
```

`sync` runs the full pipeline for every newly accepted submission,
using the *existing* engine at every stage — nothing here reimplements
storage, rendering, or the graph:

```text
Submission (Codeforces)
    -> Problem object     (handbook.sync.mapping: rating -> Difficulty,
                            participantType -> ProblemSource, tags ->
                            algorithm topic names)
    -> Knowledge object    (models.Problem, a real KnowledgeItem)
    -> Store               (Handbook.store — same path Chunk 2/3 use)
    -> Graph update         (GraphBuilder, rebuilt over every problem
                            synced so far, not just this run's)
    -> Revision note        (a concise, structured intermediate format —
                            see below — written to `Revision Notes/`)
```

Sync is safe to run repeatedly: a submission id already recorded is
never reprocessed, and re-solving an already-known problem (say, in a
different language) never creates a second note. State lives at
`<vault>/.handbook/sync/state.json`, following the same "small JSON
file, atomic write" convention `handbook.core.index` already
established.

**Revision notes are intentionally not final notes.** Only what's
mechanically derivable from Codeforces' own data is filled in
automatically — the problem's metadata, its tags/rating as a
"recognition" cue, and a factual count of failed attempts before the
AC. The sections that require actually understanding the solution
(**Core Idea**, **Complexity**, **Key Observation**, **Implementation
Trick**) are left blank, marked clearly in the rendered Markdown, for a
human to fill in while converting the note into a handwritten one. This
prototype does no AI reasoning and does no handwriting generation —
both are explicitly future work; see `handbook/sync/revision_note.py`
for the intermediate format a future handwriting renderer would
consume.

## Testing

```bash
uv run pytest -q
uv run ruff check src tests
```

## Out of scope

**Knowledge model layer (Chunk 2):** revision scheduling, duplicate
detection beyond the id/slug policy above, and resolving `Relation`
data into an actual traversable graph or search index are not
implemented — the models are built *for* those features, not as them.

**Beautiful Note System (Chunk 3):** search, MCP, AI workflows (writing
or merging content into the `<!-- ai:*:start/end -->` sections), graph
indexing, and duplicate detection are explicitly not part of this pass.
Mermaid diagrams and Dataview queries are rendered as static text from
each item's own fields; nothing here builds a cross-note index, and
storage still does not read a file back before overwriting it.

**Knowledge Graph (Chunk 4A):** dashboards, a recommendation engine,
learning paths, a revision engine, weak-topic discovery, AI/embeddings/
LLM-backed semantic duplicate detection, and MCP are all explicitly not
part of this pass — this chunk is the graph *engine* those features will
be built on top of, not any of the features themselves. `DuplicateDetector`
is exact/fuzzy-string-based only, with a pluggable seam
(`extra_detectors`) for a later semantic pass. The graph is also not yet
wired up to a real vault loader — `GraphBuilder` takes `KnowledgeItem`
instances directly; reading them back from the Markdown vault on disk is
future work.

**Codeforces Sync:** AI reasoning, MCP, handwriting generation, and any
recommendation engine are explicitly not part of this pass. Revision
notes leave Core Idea/Complexity/Key Observation/Implementation Trick
blank by design — no attempt is made to infer them, mechanically or
otherwise. Only `Problem` KnowledgeItems are created (no `Algorithm`/
`Pattern`/`Mistake` items); tags become `Problem.algorithms` relations
by name, which the graph resolves to shadow nodes until a real note for
that topic exists. There's still no vault loader: the graph is rebuilt
each run from `SyncState`'s own record of previously-synced problems,
not by reading the vault's rendered Markdown back in. Contest names are
not resolved (the numeric Codeforces contest id is used as-is) — a
`contest.list` lookup would be a natural, cheap follow-up. Only
Codeforces is supported; other judges (AtCoder, LeetCode, etc.) would
need their own client alongside `handbook.sync.codeforces`.
