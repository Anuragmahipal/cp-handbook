# Learning Intermediate Representation — Architecture Notes

## Where this sits

```
handbook.learning            (this chunk — new, standalone package)
      │
      ├─ versioning.py   LIRModel / Identified / Revisable / supersede()
      │                  (the immutable base every other model builds on)
      │
      ├─ enums.py         every enumeration used across the representation
      ├─ richtext.py       Span, RichText   (structured inline text)
      │
      ├─ blocks.py
      │     TextBlock, CodeBlock ──────────────────┐
      │     VisualBlock, Arrow, Connection          │  → Block (discriminated union)
      │     DiagramBlock (elements/arrows/conns)    │
      │     Callout (body: TextBlock | CodeBlock) ──┘
      │
      ├─ review.py         MemoryAnchor (content) / ReviewCue (state)
      │
      ├─ page.py
      │     PageMetadata
      │     Section (Revisable: blocks + memory_anchors + review_cues)
      │     Page     (Revisable: metadata + sections, schema_version)
      │
      ├─ path.py           PathStep, LearningPath (Revisable, schema_version)
      │
      ├─ serialization.py  dump_page / load_page / dump_learning_path /
      │                    load_learning_path (schema-version-gated JSON)
      │
      └─ examples.py        build_example_page() — "Binary Search on the Answer"

handbook.models   (Chunk 2 — CP domain knowledge)         ─┐
handbook.core / handbook.renderers   (Markdown + storage)   ├─  UNTOUCHED.
handbook.sync   (Codeforces sync pipeline)                 ─┘  Zero imports
                                                                either direction.
```

Nothing in `handbook.learning` imports from `handbook.models`,
`handbook.core`, `handbook.renderers`, or `handbook.sync`, and nothing
in those packages imports from `handbook.learning`. This was a hard
constraint on the chunk ("do not touch sync / Codeforces / Markdown"),
and it's enforced by construction, not by convention: there was never
an import statement to write. A byte-for-byte diff against the
pre-chunk source tree confirms every existing file is untouched.

## Key decisions and why

**Immutable, `tuple`-based, `extra="forbid"`.** Every model here is
frozen. This is a deliberate departure from `KnowledgeItem`
(mutable, `list`-based fields, permissive extras), because this
package plays a different role: `KnowledgeItem` is one system's
working record of a piece of knowledge; the LIR is meant to be read
concurrently by an unknown number of future renderers (Markdown,
canvas, flashcards, slides, PDF, handwriting) that must never be able
to perturb each other's view of the same `Page`. "Editing" a page here
means producing a new `Page`, not mutating the one renderers already
hold a reference to. `extra="forbid"` closes the vocabulary: nothing
renderer-specific (a CSS class name, a pixel offset, an SVG path) can
sneak in through a permissive schema.

**Two-layer versioning, not one.** `schema_version` (a field only on
`Page` and `LearningPath`, the two serialization roots) is the version
of the *format itself* — bumped when this package's shape changes in a
breaking way. `version`/`revision_of`/`superseded_by` (on every
`Revisable`: `Page`, `Section`, `LearningPath`) is the version of one
specific piece of *content* — bumped every time it's revised. Conflating
these would make it impossible to tell "this JSON is from an
incompatible version of the package" apart from "this is just an old
draft of this section," which need completely different handling by a
caller.

**`revise()` returns a new object; only `supersede()` touches the
old one, and only ever returns a copy.** Because everything is frozen,
there was no way to make revision a single mutating call, so it's
deliberately two pure functions instead of one: `section.revise(...)`
answers "what would the next version look like", and
`supersede(old, new)` answers "here's `old`, flagged as superseded by
`new`" without ever mutating `old` itself. A caller that computes a
revision and decides not to keep it hasn't changed anything — this
directly implements the "student's own prior understanding being
corrected is a visible, nameable moment, not a silent overwrite"
behavior from the study-partner interaction spec this chunk follows.

**`VisualBlock` is deliberately both a `Block` and a diagram element.**
The object list for this chunk names `VisualBlock` and `DiagramBlock`
separately, but nothing about "a single visual thing with a role,
label, and optional value" changes meaning depending on whether it has
neighbors. A `VisualBlock` can sit alone in `Section.blocks` (one
standalone highlighted state) or as one of many in
`DiagramBlock.elements` (one node among several, connected by `Arrow`/
`Connection`). One object, reused, instead of a `DiagramNode` class
that would have duplicated `VisualBlock` field-for-field.

**`Arrow` vs `Connection` is a semantic split, not a styling one.**
`Arrow` is directed and represents *flow* — a pointer moving, a
recursive call, a state transition firing; `order` lets several arrows
be sequenced as steps rather than shown all at once. `Connection` is
structural — adjacency, grouping, equivalence — something that is
simply true rather than something happening. A renderer that wants to
animate a walkthrough step-by-step only needs to look at `arrows`,
ordered; one that wants to draw the static shape of a graph only needs
`connections`.

**`MemoryAnchor` (content) and `ReviewCue` (state) are two objects, not
one, and the scheduling algorithm is out of scope.** An anchor is
authored once, as part of the page, and is a *compressed cue* pointing
at the block that holds the real explanation — never a duplicate of
that explanation, following the same "relations as data, not copies of
content" pattern the domain model already uses for typed relationships.
A `ReviewCue` carries the state a spaced-repetition scheduler would
read and write (`status`, `strength`, `review_count`,
`last_reviewed_at`, `next_due_at`) — this package stores that state and
validates that every cue references a real anchor, but does not
implement the algorithm that updates it. Building that algorithm is
future work for a review-engine chunk, not this one.

**Validation is structural, checked at construction time, not deferred
to a later pass.** `DiagramBlock` rejects an `Arrow`/`Connection`
whose endpoint isn't one of its own `elements`. `Section` rejects a
`MemoryAnchor` whose `target_id` isn't the section's own id or one of
its blocks', and a `ReviewCue` whose `anchor_id` isn't one of the
section's own anchors. `Page`/`Section`/`LearningPath` all reject
duplicate ids among their children. None of this needs a second
"validate the whole tree" pass — by the time a `Page` object exists at
all, every cross-reference inside it is already known-good.

**No slug, no filesystem path, anywhere in this package.** An earlier
draft added a `PageMetadata.slug` computed field to mirror
`KnowledgeItem.slug`. It was removed for two reasons: mechanically, a
Pydantic computed field appears in `model_dump_json()` output but
isn't a constructor argument, which broke round-tripping the instant
`extra="forbid"` was in play. More fundamentally, a filesystem-safe
slug is a storage/rendering concern — exactly the kind of thing a
Markdown renderer or a storage engine should own, not the
representation itself.

## What's explicitly deferred

- **The `KnowledgeItem` → `Page` bridge.** Nothing here reads a
  `Problem`/`Algorithm`/`Mistake` and produces a `Page`. This chunk
  builds the target language; projecting the existing domain model
  into it is a natural next chunk, deliberately not this one (per the
  "do not touch" constraints).
- **Every renderer.** No Markdown output, no canvas output, no
  flashcard/slide/PDF output. `Page`/`LearningPath` are proven
  expressive enough to describe the content those renderers would need
  (see `examples.py`), but none of them are built here.
- **The spaced-repetition/review-scheduling algorithm.** `ReviewCue`
  carries the state such an algorithm reads and writes; computing
  `next_due_at` from a review outcome is not implemented.
- **Schema migrations.** `SchemaVersionError` and the `schema_version`
  field establish the seam a migration would hook into; no migration
  from one version to another is implemented, since there is only ever
  one version so far.
- **A `LearningPath` ↔ `Page` consistency check.** `PathStep.page_id`
  is a plain string reference, unresolved and unvalidated against any
  actual `Page` — the same "relation as data, not a foreign key"
  choice the domain model's graph layer already made for exactly the
  same reason (resolution is a job for a layer that actually has an
  index of pages to resolve against).
