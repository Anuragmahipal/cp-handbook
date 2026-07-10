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
