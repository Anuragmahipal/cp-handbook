"""RevisionNote: the concise, structured intermediate revision format.

This is deliberately **not** a :class:`~handbook.models.base.KnowledgeItem`
and does not go through :meth:`~handbook.handbook.Handbook.store` or the
knowledge graph -- it's a separate, downstream artifact meant to be
consumed by a future handwriting-generation step (out of scope for this
prototype; see the module docs on ``handbook.sync``). It is also
deliberately **not** prose: every section is a short phrase or a single
sentence, since a handwriting renderer works from cues, not paragraphs.

Only what's mechanically derivable from Codeforces' own metadata is
filled in automatically (``recognition``, ``mistake``); everything that
would require actually understanding the solution (``core_idea``,
``complexity``, ``key_observation``, ``implementation_trick``) is left
blank for a human to fill in by hand -- see
:mod:`handbook.sync.note_writer`, where the rendered Markdown marks
each blank section clearly rather than silently omitting it.
"""

from __future__ import annotations

from collections import Counter
from datetime import datetime

from pydantic import BaseModel, Field

from handbook.models import Problem, Submission
from handbook.sync.codeforces import CFSubmission


class RevisionNote(BaseModel):
    """One problem's concise revision scaffold.

    ``problem_id`` links back to the stored ``Problem`` KnowledgeItem
    this note was generated from, so a future renderer (or a human) can
    always find the full knowledge-base entry behind a given note.
    """

    problem_id: str
    problem_title: str
    platform: str
    contest: str
    index: str
    url: str
    rating: int | None
    tags: list[str]
    source: str
    solved_at: datetime

    # -- mechanically derived from Codeforces metadata -----------------
    recognition: str = ""
    """What signaled which technique to reach for -- here, just the
    problem's own tags and rating, since Codeforces tags *are* the
    recognition cues for a solved problem."""
    mistake: str = ""
    """A factual count and sequence of failed attempts before this AC,
    by verdict -- not a guess at *why* they failed, just what Codeforces
    recorded. The full verdict sequence is preserved so the learning
    narrative remains visible (e.g. WA -> WA -> TLE -> AC)."""
    verdict_sequence: list[str] = []
    """The chronological sequence of all verdicts for this problem,
    including the final AC. E.g. ["WRONG_ANSWER", "TIME_LIMIT_EXCEEDED", "OK"]."""

    # -- left blank for a human to fill in by hand ----------------------
    core_idea: str = ""
    complexity: str = ""
    key_observation: str = ""
    implementation_trick: str = ""

    generated_at: datetime = Field(default_factory=datetime.now)


def _recognition_text(item: Problem) -> str:
    parts: list[str] = []
    if item.tags:
        parts.append("Tags: " + ", ".join(item.tags))
    if item.rating is not None:
        parts.append(f"Rating {item.rating}")
    return " — ".join(parts)


def _mistake_text(submission_history: list[Submission]) -> str:
    """Build a factual description of failed attempts from the full
    submission history.
    """
    # Filter to only non-AC submissions that occurred before any AC
    ac_indices = [
        i for i, s in enumerate(submission_history) if s.accepted
    ]
    first_ac_index = ac_indices[0] if ac_indices else len(submission_history)
    prior_wrong = submission_history[:first_ac_index]
    prior_wrong = [s for s in prior_wrong if not s.accepted]

    if not prior_wrong:
        return "Solved on the first attempt."

    verdict_counts = Counter(s.verdict or "UNKNOWN" for s in prior_wrong)
    breakdown = ", ".join(
        f"{count}x {verdict}" for verdict, count in verdict_counts.most_common()
    )
    plural = "attempt" if len(prior_wrong) == 1 else "attempts"
    return f"{len(prior_wrong)} failed {plural} before AC: {breakdown}"


def _verdict_sequence(submission_history: list[Submission]) -> list[str]:
    """The chronological verdict sequence, including the final AC."""
    return [s.verdict or "UNKNOWN" for s in submission_history]


def generate_revision_note(
    item: Problem,
    submission: CFSubmission,
    submission_history: list[Submission],
) -> RevisionNote:
    """Build the intermediate revision note for a just-synced ``Problem``.

    ``submission`` is the accepted submission the note is generated
    from; ``submission_history`` is the complete, chronologically-sorted
    list of all submissions for this problem (including non-accepted ones).
    """
    return RevisionNote(
        problem_id=item.id,
        problem_title=item.title,
        platform=item.platform.value,
        contest=item.contest,
        index=item.index,
        url=item.url,
        rating=item.rating,
        tags=list(item.tags),
        source=item.source.value,
        solved_at=submission.creation_time,
        recognition=_recognition_text(item),
        mistake=_mistake_text(submission_history),
        verdict_sequence=_verdict_sequence(submission_history),
    )
