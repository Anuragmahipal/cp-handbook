# Codeforces Sync — Developer Notes

## Quick start

```bash
uv sync
uv run cp-handbook init      # prompts for handle + vault if not passed as flags
uv run cp-handbook sync
uv run cp-handbook status
```

`init`/`sync` also accept non-interactive flags directly:
`cp-handbook init --handle tourist --vault ~/cp-vault`.

## Why the pipeline is structured the way it is

**Two-pass dedup, keyed differently.** A Codeforces *submission* id and
a Codeforces *problem* are deduplicated separately, because they answer
different questions. `SyncState.has_imported(submission_id)` answers
"have I already looked at this exact judged attempt" — every accepted
submission is marked imported, even the second, third, etc. AC on the
same problem. `SyncState.has_problem(problem_key)` answers "does this
vault already have a note for this problem" — only the *first* AC for
a given problem ever creates a `Problem`/revision note. Conflating
these (e.g. only tracking problem keys) would silently reprocess a
resubmission in a new language forever; conflating them the other way
(only tracking submission ids) would let a re-solve create a duplicate
note.

**The graph is rebuilt from `SyncState`, not from the vault.** Reading
a `KnowledgeItem` back off its rendered Markdown (a real "vault loader")
was explicitly out of scope for Chunk 4A, and still is here.
`SyncState` keeps its own serialized copy of every previously-synced
`Problem` specifically so `GraphBuilder` always has the *full*
cumulative set of known problems to build from, not just the current
run's new ones — without needing to parse anything back out of
Markdown. The tradeoff: if someone hand-edits a `Problem` note's
frontmatter directly in Obsidian, that edit is invisible to the graph
until a real vault loader exists. Worth knowing; not a regression
introduced here, since nothing before this could read edits back either.

**Notebook pages are recompiled from that same full graph, every run.**
After the graph is rebuilt, `handbook.sync.notebook.
compile_notebook_pages()` runs every known item through
`KnowledgeCompiler` and `NotebookRenderer`, writing
`Vault/Notebook/<Kind>/<slug>.html` — the same "rebuild from
everything known, not just this run's delta" choice the graph itself
already makes, extended one layer further. See
`docs/ARCHITECTURE_NOTES_COMPILER.md` for the compiler itself; this
module only orchestrates calling it and writing the result next to
(never inside) the existing Markdown note folders.

**Codeforces tags become `Problem.algorithms` relations, not just
`Problem.tags`.** They're written to both. This was a deliberate choice
to make the knowledge graph substance out of real synced data — tags
resolve to shadow nodes (e.g. "Dynamic Programming") when no matching
Algorithm note exists yet, which is exactly the graph's existing
shadow-node mechanism working as designed. Once a real "Dynamic
Programming" Algorithm note is added by hand, every problem that's ever
been tagged `dp` retroactively connects to it on the next sync (the
graph is rebuilt from scratch every run, so this "just happens").

**Title collisions are handled, not just tested around.** Two different
Codeforces problems can share an exact title (it happens — contests
reuse generic names like "Sum" or "Array"). `Handbook.store()` already
and correctly refuses this as a duplicate. The pipeline catches that
specific error once and retries with the title disambiguated using the
(globally unique) `contestId+index` — see `_store_with_title_collision_
handling` in `pipeline.py`. This was found by writing the test for it,
not anticipated up front — worth flagging in case a similar collision
shape shows up elsewhere later.

**`SyncConfig` deliberately doesn't touch `handbook.settings.Settings`.**
That class is a module-level singleton read once at import time, which
makes it a poor fit for (a) writing new values back, or (b) test
isolation. `SyncConfig.load()`/`.save()` read/write the *same physical
file* fresh every call, so there is exactly one config file for the
whole project, but two independent, differently-scoped readers of it —
much like two `git` invocations coordinating through `.git/config`
rather than shared process memory.

## Known simplifications (called out, not hidden)

- **Contest names aren't resolved.** `Problem.contest` is the raw
  numeric Codeforces contest id, not a human-readable round name. A
  `contest.list` API call, cached, would fix this cheaply — skipped
  here to keep the network surface (and the test-mocking surface) to
  exactly one endpoint.
- **`time_spent_minutes` is a proxy, not a measurement.** It's
  `relativeTimeSeconds` at the moment of the accepted submission (time
  since contest start), which is only meaningful for submissions made
  during a live contest window — guarded against Codeforces' own
  out-of-contest sentinel value (`2^31 - 1`), but still just a proxy
  for "time spent," not a real one.
- **Only Codeforces.** Adding another judge means writing its own
  client alongside `codeforces.py` (fetch + parse) and its own mapping
  module; `pipeline.py`, `state.py`, and everything downstream of a
  `Problem` KnowledgeItem needs no changes to support a second judge.
- **No `Algorithm`/`Pattern`/`Mistake` items are created.** Only
  `Problem`. A tag becomes a *reference* to a topic, not a new
  first-class note — creating real Algorithm notes automatically from
  tag names would be guessing at content this prototype has no
  business guessing at. `compile_notebook_pages()` is nonetheless
  written generically against whatever `SyncState.known_items()`
  returns, not hardcoded to `Problem` — so this limitation lives here,
  in what sync *creates*, not in what gets compiled once created.

## Testing notes

- Every Codeforces-facing test goes through `CodeforcesClient(transport=
  fake_transport)` — a plain function from URL to raw JSON bytes. No
  `unittest.mock`, no monkeypatching `urllib` globally, no real network
  access, ever, in the test suite.
- CLI tests call `handbook.sync.cli.main(argv, config_path=..., client=
  ...)` directly rather than shelling out to the installed script. This
  exercises the exact same `argparse`/dispatch code a real invocation
  does; the only thing it doesn't cover is process-boundary concerns
  (nothing in this CLI depends on those). The installed console script
  itself was separately verified with `uv sync && uv run cp-handbook
  --help` for each subcommand.
- `tests/conftest.py` gained one new fixture, `cf_submission_payload`
  — a factory for a raw `user.status` submission dict, matching
  https://codeforces.com/apiHelp/objects#Submission. Every sync test
  file uses it instead of hand-rolling the same JSON shape repeatedly.
- `tests/test_sync_notebook_compilation.py` covers the notebook-
  compilation stage specifically: one `.html` per synced problem,
  written next to (not inside) the Markdown note folders, stable
  across repeated syncs, both at the `run_sync()` and CLI level. The
  compiler itself has its own test suite — see
  `docs/ARCHITECTURE_NOTES_COMPILER.md`'s "Testing" section.

## What would come next (not built here, on purpose)

- A real vault loader (parse `Problem` notes' frontmatter back into
  KnowledgeItems), which would let the graph reflect hand-edits made
  directly in Obsidian and remove `SyncState`'s own item cache.
- `contest.list` integration for real contest names.
- A second judge client (AtCoder is the natural next one, given a
  similarly simple public API).
- Everything explicitly excluded by this task: AI-assisted note
  filling, handwriting generation from the intermediate format, MCP,
  and any recommendation/spaced-repetition engine.
