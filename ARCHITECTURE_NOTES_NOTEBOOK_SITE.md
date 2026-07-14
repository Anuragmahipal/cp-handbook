# Architecture Notes: Notebook Site (navigation, timeline, dashboard)

## Where this sits

`handbook.sync.notebook_site.build_notebook_site()` is the last step
in `run_sync()`, after materialization:

```
Problems (SyncState) + materialized items (MaterializationEngine)
    -> GraphBuilder                      (unchanged, reused)
    -> KnowledgeCompiler + NotebookRenderer   (unchanged, reused, called directly)
    -> link map + nav groups + shared timeline
    -> per-page chrome (linkify + breadcrumbs + prev/next + sidebar)
    -> Notebook/<Kind>/<slug>.html
    -> Notebook/index.html                (dashboard)
```

It does not replace `handbook.sync.notebook.compile_notebook_pages()`.
That function, and its own tests and golden-snapshot contract, are
untouched -- `run_sync()` calls it exactly as before, then separately
calls `build_notebook_site()` over a *different* graph (Problems +
materialized items) to produce the richer, linked, chrome-wrapped
version of the same idea. See "Why two compile passes" below.

## The problem this solves

Every notebook page, before this chunk, was correct but alone.
`docs/ARCHITECTURE_NOTES_NOTEBOOK.md` already named this as deferred:
"no cross-page nav chrome, table of contents across pages, or asset
sharing between multiple rendered pages yet." Concretely:

- A related-item reference (`handbook.renderers.notebook.blocks_html`)
  rendered as `<span class="lir-link" title="{node id}">`, never an
  `<a href>` -- because `NotebookRenderer` renders one `Page` at a
  time and has no way to know where any other page will end up on
  disk. The chunk brief's "Everything clickable" was, until now,
  nothing clickable.
- There was no dashboard, so no single place answered "what do I
  actually know, and what's weak."
- There was no shared history view -- no per-page sense of "what did I
  learn, in what order."

## Key decisions and why

**A post-processing layer, not a renderer change.** The chunk brief is
explicit: do not redesign `NotebookRenderer`. Concretely, that means
this module only ever reads `RenderResult.html`/`.css` -- the
renderer's already-public output -- and never its internals
(`_wrap_document`, `_render_row`, etc.). Cross-page linkification
works by finding every `<span class="lir-link" title="...">` in the
*rendered* HTML and, once every other page's URL is known (which the
renderer itself can't know), swapping it for a real `<a href>`. If
`NotebookRenderer`'s document shell ever changes shape, `_extract_body`
falls back to embedding the whole original document in an `<iframe
srcdoc>` rather than crashing the site build over one page --
degraded, not broken.

**Why two compile passes instead of one smarter one.**
`compile_notebook_pages()` already has its own test suite and a
golden-snapshot contract (`tests/test_sync_notebook_compilation.py`,
`tests/test_compiler_golden.py`) built on it writing exactly
`NotebookRenderer`'s own output, one problem in, one page out. Bending
it into a second "site" mode risked either breaking that contract or
smuggling a parallel code path into a function whose whole value is
being simple and predictable. Calling `KnowledgeCompiler` +
`NotebookRenderer` a second time from `build_notebook_site()` costs
an extra compile+render pass per item (measured: not the bottleneck --
see Performance notes) in exchange for `compile_notebook_pages()`
staying byte-for-byte what it always was. A future chunk that gives
`compile_notebook_pages()` an official post-processing hook could
collapse these into one pass without changing either one's outward
contract.

**One graph for authored counts, a second graph for the site.**
`SyncReport.graph_node_count`/`.graph_edge_count`/`.duplicate_report`
describe the vault's *authored* Problems alone (existing tests assert
exact values on this). `build_notebook_site()` needs a graph that also
includes materialized items, or every Problem -> Algorithm/Pattern/
Mistake/Contest relation would still resolve to a shadow node instead
of the real, now-persisted one. `run_sync()` therefore builds `graph`
(unchanged, for the existing report fields) and a separate
`site_graph` (Problems + materialized items, for the site) rather than
mutating one graph's meaning mid-pipeline.

**The learning timeline is one shared feed, not per-page-filtered.**
The chunk brief's own worked example ("July 2025 Solved Candies / Aug
2025 Solved Ropes / Sep 2025 Repeated Off By One / ...") reads as one
chronological history of the whole vault, not a different slice per
page. Every item's own `created_at` becomes one event (no fabricated
timestamps); events are computed once per `build_notebook_site()` call
and the identical HTML fragment is embedded on every page -- cheap,
and exactly matches "the same sidebar" as read in the brief. Capped at
the most recent 60 events so a large vault's sidebar stays a sidebar,
not the whole vault's history rendered on every request.

**"Most Used" / "Weak Areas" / mastery counts are computed live from
the graph, never from a stored counter.** `Mistake.occurrences` exists
on the model and is designed to be bumped by re-storing the item -- but
this chunk's materialized items are never re-stored (see
`docs/ARCHITECTURE_NOTES_MATERIALIZATION.md`), so that field would go
stale immediately. Backlink counts from `KnowledgeGraph.related(...,
direction="in")`, filtered by `edge.provenance == "field:{name}"`, are
recomputed fresh every `cp-handbook sync` from whatever Problems
currently exist -- always current, at the cost of being an
inference from the graph rather than an authored number. Review-queue
and mastery counts are pulled the same way, from every compiled
`Page`'s `ReviewCue`s (`handbook.learning.review`), not a separate
statistic.

**Breadcrumbs' middle segment links somewhere real.** A page's
breadcrumb (`Notebook / Algorithms / Binary Search`) links its
`Algorithms` segment to `../index.html#algorithms`. The dashboard's
"Browse by Kind" section is what that anchor resolves to -- one card
per kind, `id="{folder.lower()}"`, listing every compiled page of that
kind (not just a top-N slice, unlike Recently Solved/Weak
Areas/Most Used). Without it, "Everything clickable" would have had
one dangling link on every single page.

**Prev/next ordering is alphabetical by title, within kind.**
Simplest deterministic ordering available without inventing a
"curriculum order" the codebase has no data to support. Chronological-
by-`created_at` was the other candidate; alphabetical was chosen so a
person can predict what "next" means without needing to check the
timeline first, and so the ordering doesn't silently reshuffle as new
items get materialized mid-alphabet.

**Own CSS, not `NotebookTheme`.** The site chrome (sidebar,
breadcrumbs, dashboard cards) styles the *shell* around a page, never
a page's own content -- `RenderResult.css` is still what styles
everything inside `.lir-container`. Keeping the two independent avoids
coupling this module to `renderers/notebook/theme.py`'s internals for
no real benefit; the palette was chosen to loosely match
`NotebookTheme.light_notebook()`'s warm, paper-like tones so the two
don't visually clash sitting on the same page.

**Regenerated wholesale every run, on purpose.** Same reasoning
`docs/ARCHITECTURE_NOTES_COMPILER.md` already established for
`compile_notebook_pages()`: nothing this module writes is a source of
truth, so there's nothing to lose by recomputing it from scratch every
`cp-handbook sync`. This is what lets "never regenerate everything
blindly" (the chunk brief's own words) hold at the level that actually
matters -- a person's Markdown notes are never touched by this module,
ever -- without needing to build incremental HTML patching for a view
that has no persistent state of its own.

## What's explicitly deferred

- **Per-item-scoped timeline filtering.** The sidebar is one global
  feed on every page. Filtering it to "events related to this item"
  would need the graph threaded into timeline construction and a
  definition of "related" precise enough to not just be Weak
  Areas/Most Used again under a different name.
- **A `Notebook/<Kind>/index.html` per-kind index page.** The
  dashboard's "Browse by Kind" cards cover this for now; a dedicated
  page per kind would only earn its keep once a single kind's card
  gets too long to be a dashboard section.
- **Curriculum-aware prev/next.** Alphabetical, not "what should I
  learn next" -- see above.
- Everything `docs/ARCHITECTURE_NOTES_NOTEBOOK.md` already deferred
  and this chunk didn't pick up: Topic compilation, diagrams
  synthesized from metadata, spaced-repetition scheduling.

## Performance notes

Building the full site (compile + render + linkify + chrome +
dashboard) for 240 Problems plus their 68 materialized items -- 308
pages total -- took ~420ms on a single core; end-to-end
`materialize + graph build + site build` was ~590ms. A second run over
the same data (nothing new to materialize, but the site is still
rebuilt wholesale, by design) was ~330ms. For a personal CP notebook's
realistic scale (hundreds, not tens of thousands, of items), this
comfortably fits inside a `cp-handbook sync` a person runs after a
practice session, not a background job.

## Testing

- `tests/test_notebook_site.py` -- `build_notebook_site()` in
  isolation: one page per compilable item plus a dashboard,
  unsupported kinds skipped, `lir-link` placeholders become real
  `href`s (and gracefully don't when the target isn't compiled),
  breadcrumbs/back-to-dashboard/prev-next present and correctly
  ordered (including at the first/last item), timeline chronological,
  dashboard stats reflect live graph backlink counts, breadcrumb
  kind-anchors resolve to a real dashboard section, node/edge counts
  match the input graph, safely rerunnable.
- `tests/test_sync_materialization_integration.py` also covers the
  site end-to-end through `run_sync()`: a synced Problem's page really
  does link to its materialized Algorithm's page on disk.
