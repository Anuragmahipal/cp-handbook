# Notebook Renderer — Architecture Notes

## Where this sits

```
handbook.renderers.notebook   (this chunk — new, standalone package)
      │
      ├─ theme.py         NotebookTheme + 3 built-in presets
      │                   (Light Notebook / Dark Notebook / Handwritten)
      │
      ├─ layout.py         LayoutEngine — deterministic, weight-based
      │                    grouping of Sections into LayoutRows
      │
      ├─ syntax.py           CSS-only syntax highlighting (regex tokenizer,
      │                      cpp/c/java/javascript/python + generic fallback)
      │
      ├─ svg.py                SVGRenderer — DiagramBlock → inline <svg>,
      │                        grid layout + automatic edge routing/clipping
      │
      ├─ blocks_html.py          block-level + inline HTML rendering,
      │                          dispatches on Block.block_type
      │
      ├─ css_template.py           theme tokens → the one stylesheet
      │
      ├─ result.py                   RenderResult (html + css + assets)
      │
      └─ renderer.py                   NotebookRenderer (the entry point)

handbook.learning     (Chunk: LIR — COMPLETE, STABLE)        ─┐
handbook.models / graph / sync / core (storage)              ├─  UNTOUCHED.
handbook.renderers.markdown_renderer, filters, __init__.py   ─┘  Verified
                                                                  byte-identical
                                                                  to before
                                                                  this chunk.
```

`handbook.renderers.notebook` imports **only** from `handbook.learning`
(the LIR) and two small, generic, non-domain utilities
(`handbook.utils.filesystem.atomic_write`, used by
`RenderResult.write`). It does not import from `handbook.models`,
`handbook.graph`, `handbook.sync`, `handbook.core`, or
`handbook.renderers.markdown_renderer`/`filters`, and nothing in those
imports from it. A byte-for-byte diff against the pre-chunk source
tree confirms every one of them, plus every LIR file, is untouched.

## Key decisions and why

**Not a subclass of `handbook.core.renderer.Renderer`.** That interface
is `render(item: KnowledgeItem) -> str` — one domain type in, one
string out. `NotebookRenderer.render` takes a domain-independent `Page`
and returns a `RenderResult` (html + css + assets). Forcing a shared
base class would mean either bending `Renderer` to accept a `Page`
(coupling it to the LIR) or bending `RenderResult` down to a bare
string (losing the separate `css`/`assets` a future renderer might
need). Two renderers with genuinely different shapes are better served
by two small, honest interfaces than one interface stretched to cover
both.

**Layout is a weight-based bin-pack, not a hardcoded slot list.** The
brief's example layout names specific sections ("Recognition", "Core
Idea", "Diagram", ...) — but `Page.sections` in the LIR is an arbitrary
ordered list with no reserved names; the representation is
domain-agnostic by design (see `ARCHITECTURE_NOTES_LEARNING.md`). So
`LayoutEngine` groups purely on content: a section's "weight" comes
from what block types it contains (a `DiagramBlock` always forces a
full-width row — diagrams need room to stay legible; a `CodeBlock`
adds weight; extra blocks add a little more), and rows fill
greedily, in original reading order, up to a capacity of 3 units or 3
columns. Same input, same output, always — verified directly in
`test_notebook_layout.py`, and indirectly by every golden test passing
across independent process runs.

**"No absolute positioning" applies to the page, not to diagrams.**
Every row in the HTML document is a normal flex container; nothing on
the page itself has a fixed `x`/`y`. Inside one `<svg>`, node
coordinates obviously exist — that's inherent to vector graphics, not
a violation of the constraint. `SVGRenderer` computes those
coordinates itself, from each element's `ElementPosition(row, col)`
(or auto-placement when unset), and owns the entire coordinate system;
nothing about it is hand-specified pixel data from a diagram's author.

**Automatic arrow routing, concretely: edge-clipped straight lines for
same-row/same-column pairs, a two-segment orthogonal elbow otherwise.**
Both endpoints are clipped to the boundary of whatever box (or nominal
marker/label footprint) they're leaving/entering, using the standard
"scale toward target until you hit the box edge" technique — so an
arrow never visually overlaps the node it's pointing at. This is
deliberately not a general obstacle-avoiding pathfinder (no collision
detection against other nodes/edges); for the two-or-three-hop
diagrams a study note actually needs, a deterministic elbow reads
cleanly and needs no author-specified waypoints, which is what
"automatic" means here.

**`Arrow.order` gets a real, visible effect in a static image.** Since
there's no animation (static SVG only, no JS), an ordered arrow gets a
small numbered badge at its source end instead of being silently
ignored. A two-step walkthrough (see the pattern-page example) reads
as "1, then 2" without needing interactivity.

**Syntax highlighting is a small regex tokenizer, not a language
server.** One shared token pattern (block comment / line comment /
string / number / identifier), one keyword set per language family
(cpp/c, java/javascript, python), and a generic fallback for anything
else that still colors strings/numbers/comments without a keyword
list. Good enough to make CP code readable; not a claim to correctly
tokenize every language's full grammar. Operates one line at a time
(no multi-line comment state carried across lines) because `CodeBlock`
is rendered one `<tr>` per line for line numbers and per-line
`CodeAnnotation`s — see `syntax.py`'s docstring for the trade-off.

**`CalloutKind` styling covers what the LIR actually has, not the
brief's exact words.** The brief asks for distinct styles for "Tip,
Warning, Mistake, Idea, Definition, Review." The LIR's `CalloutKind`
enum (frozen, per the "do not touch LIR" constraint) has
`tip`/`warning`/`mistake`/`insight`/`definition`/`example`/`question` —
no `idea` or `review` value. `insight` is styled as the "Idea" callout
kind was meant to be; "Review" styling is delivered as `ReviewCue`
badges (`NEW`/`LEARNING`/`DUE`/`MASTERED`/`SUSPENDED`), which is what
the brief's own "Review Cues" section actually specifies — there was
never a need to add a value to a stable enum to satisfy this.

**Determinism required one real fix, not just a design intention.**
The first pass derived each diagram's SVG `<marker>` id from
`DiagramBlock.id` directly. That id defaults to a random UUID when a
caller doesn't pin one explicitly (correct LIR behavior — see
`versioning.py`'s `Identified`), which `handbook.learning.examples.
build_example_page()` mostly doesn't for objects other than diagram
elements. Two independent renders of "the same" example page (freshly
constructed each time, as a caller naturally would) therefore produced
byte-different HTML — caught by running the golden tests in two
separate Python processes, not by running them twice in one process
(which shares no such hazard, since the ids only get generated once).
The fix: `NotebookRenderer.render` now hands every diagram a
render-order index (a fresh `itertools.count()` per call), and
`SVGRenderer` uses that as the marker id instead of the diagram's own
id. Determinism now depends only on block order, which the LIR does
guarantee (see `ARCHITECTURE_NOTES_LEARNING.md`'s "Section" section).
`test_notebook_renderer.py` covers idempotency (same object, called
twice) and cross-object determinism (same content via
`dump_page`/`load_page`); the golden tests were regenerated and
re-verified in a fresh process afterward. This is exactly the kind of
bug a "renders the same input the same way" claim should be checked,
not assumed.

**Themes are literal presets, not just a documented seam.** Light
Notebook (default), Dark Notebook, and Handwritten are all fully
implemented — cheap to add once `css_template.build()` consumes only
theme tokens, never section-specific logic, so a new theme is a new
`NotebookTheme.model_post_init`-validated set of values, nothing more.
Print is intentionally not a fourth preset: real print support needs
pagination-aware CSS (`@media print` page breaks, avoiding split
diagrams across pages) that's a different kind of work from picking
new colors, so it stays deferred rather than half-built under a
misleading name. A baseline `@media print` rule (no shadows, avoid
breaking a card mid-page) is included as ordinary CSS hygiene — not a
claim that "Print" the theme exists.

## What's explicitly deferred

- **A `Page` resolver for `LearningPath`.** `render_learning_path`
  shows each step's `page_id`/`section_id` as plain text, not resolved
  page content — the LIR itself deliberately doesn't resolve that
  reference either (see `ARCHITECTURE_NOTES_LEARNING.md`), so there's
  no data to resolve against yet.
- **The Print theme**, as above.
- **Obstacle-avoiding diagram routing.** Today's orthogonal-elbow
  router doesn't check whether a path crosses another node; fine for
  small CP diagrams, would need real graph-drawing work (e.g. a
  force-directed or layered layout with edge bundling) for large ones.
- **Multi-page navigation.** Each `render()` call produces one
  self-contained page; there's no cross-page nav chrome, table of
  contents across pages, or asset sharing between multiple rendered
  pages yet (`RenderResult.assets` exists as the seam for that).
- **Real screenshots of the rendered output.** See the commit message
  / delivery notes for what's provided instead and why.
