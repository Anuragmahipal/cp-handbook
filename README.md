# CP Handbook

A structured, file-based knowledge base for competitive programming —
Algorithms, Problems, Patterns, and Mistakes — stored as plain Markdown
in a local vault, with a small Python library sitting in front of it.

This README documents the **persistence engine**: the layer every future
feature (Search, MCP, AI, auto-linking) will be built on top of.

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

## Out of scope for this chunk

Search, AI extraction, embeddings, MCP, Dataview/Mermaid integration,
auto-linking, duplicate detection (beyond the id/slug policy above), and
revision scheduling are not part of the knowledge model layer and are
intentionally not implemented here. The models are deliberately built
*for* those features — every relationship is already typed data
(`Relation`/`RelationType`) rather than free-form Markdown links — but
resolving those relationships into an actual graph, index, or scheduler
is future work, not this chunk's.
