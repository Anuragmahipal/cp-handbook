# Chunk 4A — Architecture Notes

## Where this sits

```
KnowledgeItem (Chunk 2)
      │  (in-memory instances; GraphBuilder never touches the filesystem)
      ▼
GraphBuilder.build()
      │
      ├─ pass 1: Node.from_item(item)  for every item  -> GraphIndex.upsert_node
      │
      └─ pass 2: for every list[Relation] field on every item (discovered
                 generically, not hardcoded):
                     Resolver.resolve(relation.target)  -> GraphIndex.add_edge
      ▼
KnowledgeGraph(index)
      │
      ├─ .get / .related / .backlinks            (direct index reads)
      ├─ .neighbors / .reachable / .shortest_path  -> Traversal(index)
      ├─ .topological_sort / .cycle_detection      -> Traversal(index)
      ├─ .export_json / .export_dot / .export_networkx -> Exporter(index)
      ├─ .search_engine()   -> SearchEngine(index)
      └─ .duplicate_detector() -> DuplicateDetector(index)
```

`GraphIndex` is the one piece of mutable state; every other class
(`Resolver`, `Traversal`, `SearchEngine`, `DuplicateDetector`,
`Exporter`) is a stateless (or read-only) collaborator constructed
around a `GraphIndex` reference. `KnowledgeGraph` is a facade over the
same index, composed rather than inherited from, so each collaborator
is independently unit-testable (see `tests/test_graph_index.py`,
`test_graph_resolver.py`, `test_graph_traversal.py`, etc.) without ever
needing a full `GraphBuilder.build()` in the test.

## Key decisions and why

**Generic relation-field discovery, not a hardcoded field list.**
`GraphBuilder._relation_fields()` walks `type(item).model_fields` and
picks out anything that's a `Relation` or a non-empty
`list[Relation]`. The alternative — a table mapping
`Problem.algorithms -> USES`, `Contest.problems -> CONTAINS`, etc. —
would need updating every time Chunk 2 (or a later chunk) adds a new
relation field to any knowledge type. Since `Relation.type` is already
baked in at construction time (via each model's own
`coerce_relations(default_type=...)` validator), the generic scan needs
no per-field type knowledge at all.

**Two-pass build.** All nodes are registered before any edge is
resolved. Without this, an item whose relation points at an item that
appears *later* in the input list would incorrectly resolve to a
shadow node on first build, only to have a real node silently appear
under a different id moments later. Two passes make resolution
independent of input order, which also means `list(items)` can come
from an unordered source (a directory listing, a set) without any
special handling.

**Edge direction follows literal authorship, not relation semantics.**
`Edge.source` is always the declaring item; `Edge.target` is always
what it points at — for every `RelationType` alike, including
`PREREQUISITE`. This means `topological_sort()` on a prerequisite chain
reads "dependent, then its prerequisite" rather than "prerequisite
first" — the reverse of what a study-planner would want. This is
intentional: this chunk is required to stay generic and
relation-agnostic (no "learning paths" logic, per the constraints), so
baking in a `PREREQUISITE`-specific reversal here would smuggle in
exactly the kind of feature-specific interpretation Chunk 4B/5 is
supposed to own. `RelationType.SIMILAR_TO` / `RELATED` /
`CONTRASTS_WITH` are the one exception: they default to
`EdgeDirection.BIDIRECTIONAL` since a "similar to" edge has no
sensible single direction at all, in either authorship or semantics.
`topological_sort()`/`cycle_detection()` only walk `FORWARD` edges for
exactly this reason: a bidirectional pair is trivially a 2-cycle and
isn't a hierarchy violation.

**Shadow nodes are deterministic and deduplicated.** `Node.shadow(target)`
derives its id from `note_slug(target)`, so five different items all
referencing `"Segment Tree"` (or `"segment tree"`, or `"Segment-Tree"`)
before that note exists all converge on one shared shadow node rather
than minting five placeholders. `GraphIndex.get_or_create_shadow` is
the single choke point that guarantees this.

**`Resolver` (permissive) vs `KnowledgeGraph.get()` (strict) are
deliberately different.** `Resolver.resolve()` is used during
*construction*, where an unresolved reference must become a shadow node
so it stays visible rather than silently vanishing. `KnowledgeGraph.get()`
is used for *querying* — "does this exist" — where fabricating a node
as a side effect of a read would be a surprising, hard-to-debug
behavior. They share the same id -> slug -> alias -> title resolution
order for consistency, but only one of them creates anything.

**Exporter has no algorithmic logic, on purpose.** It only calls
`index.nodes()` / `index.edges()` and formats the result. This is what
lets `export_networkx()` exist without adding a `networkx` dependency
to the project (`pyproject.toml` is untouched) — it just produces a
dict shaped the way `nx.node_link_graph()` expects, for a caller who
already has networkx installed to consume.

**DuplicateDetector's `extra_detectors` seam.** `find_duplicates()`
takes a `Sequence[Callable[[GraphIndex], list[DuplicateGroup]]]` at
construction time and merges their output into the same
`DuplicateReport.extra` list as the built-in checks. This is where a
later embeddings/semantic-similarity detector plugs in without
`DuplicateDetector` itself changing — it only needs read access to a
`GraphIndex`, exactly like every built-in check already has.

## What's explicitly deferred (per the chunk's constraints)

- Reading `KnowledgeItem`s back off the vault (a "vault loader"/
  Markdown-plus-frontmatter parser) — `GraphBuilder` takes
  `KnowledgeItem` instances directly; wiring that up to real files on
  disk is future work, not this chunk's.
- Any relation-type-specific interpretation (study order, weak-topic
  discovery, recommendations) — the graph exposes generic primitives
  (`predecessors`, `successors`, `reachable` with a `relation_types`
  filter) that a later feature composes; it doesn't compose them
  itself.
- Semantic/embedding-based duplicate detection — the `extra_detectors`
  seam exists, but no detector is plugged in.
- Dashboards, MCP, AI, widgets — untouched; `src/mcp_server/` remains
  the same empty stub files it was before this chunk.
