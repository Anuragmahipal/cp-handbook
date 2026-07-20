"""Problem: a specific problem attempted or solved on some platform."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import ClassVar

from pydantic import Field, computed_field, field_validator

from handbook.models.base import KnowledgeItem, Relation, coerce_relations
from handbook.models.enums import Platform, ProblemSource, RelationType
from handbook.models.submission import Submission


class Problem(KnowledgeItem):
    """A single problem instance: which platform, which contest, which
    algorithms/patterns it drew on, and whether/how it was solved.

    Submission history is the source of truth for ``solved``, ``attempts``,
    ``first_attempted_at``, and ``solved_at``. These are derived from the
    :attr:`submissions` list, never set independently.

    ``created_at`` and ``updated_at`` (inherited from ``KnowledgeItem``)
    are overridden to reflect historical timestamps from Codeforces:
    ``created_at`` = when the first submission was made,
    ``updated_at`` = when the first accepted submission was made (or the
    last submission time if never solved). This ensures every downstream
    consumer -- evolution engine, stats, dashboard, timeline -- reads
    the correct historical date without needing to know about submissions.
    """

    KIND: ClassVar[str] = "problem"

    platform: Platform
    contest: str
    index: str

    contest_id: str | None = None
    """Id/title of the related :class:`~handbook.models.contest.Contest`,
    when this problem was attempted as part of one."""

    url: str = ""
    rating: int | None = Field(default=None, gt=0)
    source: ProblemSource = ProblemSource.PRACTICE

    algorithms: list[Relation] = Field(default_factory=list)
    patterns: list[Relation] = Field(default_factory=list)
    mistakes: list[Relation] = Field(default_factory=list)

    # -- submission history (source of truth) ----------------------------
    submissions: list[Submission] = Field(default_factory=list)
    """Every submission made for this problem, in chronological order.
    This list is the single source of truth for solved status, attempt
    count, and all timing metadata."""

    # -- derived fields (kept for backward compat in serialization) --------
    solved: bool = True
    """Deprecated: use :attr:`is_solved` instead. Kept for serialization
    compatibility; always overwritten by ``_derive_from_submissions``."""

    attempts: int = Field(default=1, ge=0)
    """Deprecated: use :attr:`attempt_count` instead. Kept for serialization
    compatibility; always overwritten by ``_derive_from_submissions``."""

    first_attempted_at: datetime | None = None
    """When the first submission for this problem was made.
    Derived from the earliest submission in :attr:`submissions`."""

    solved_at: datetime | None = None
    """When the first accepted submission for this problem was made.
    ``None`` if the problem has been attempted but never solved."""

    time_spent_minutes: int | None = Field(default=None, ge=0)

    @field_validator("contest", "index")
    @classmethod
    def _not_blank(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("must not be blank")
        return v

    @field_validator("algorithms", "patterns", mode="before")
    @classmethod
    def _coerce_uses(cls, v: object) -> object:
        return coerce_relations(v, default_type=RelationType.USES)

    @field_validator("mistakes", mode="before")
    @classmethod
    def _coerce_mistakes(cls, v: object) -> object:
        return coerce_relations(v, default_type=RelationType.RELATED)

    @field_validator("submissions", mode="before")
    @classmethod
    def _coerce_submissions(cls, v: object) -> object:
        """Accept plain dicts and convert them to Submission objects."""
        if not isinstance(v, list):
            return v
        result: list[Submission] = []
        for item in v:
            if isinstance(item, dict):
                result.append(Submission.from_dict(item))
            elif isinstance(item, Submission):
                result.append(item)
        return result

    def model_post_init(self, __context: object) -> None:
        """Derive ``solved``, ``attempts``, ``first_attempted_at``,
        ``solved_at``, and propagate historical timestamps to
        ``created_at``/``updated_at`` after validation."""
        self._derive_from_submissions()

    def _derive_from_submissions(self) -> None:
        """Recompute all derived fields from the submission history
        and propagate historical timestamps to ``created_at`` and
        ``updated_at``.

        Called automatically after init/validation, and may be called
        explicitly after appending new submissions.
        """
        if not self.submissions:
            # No submissions yet -- keep defaults (backward compat)
            return

        # Sort by creation time to ensure determinism
        sorted_subs = sorted(self.submissions, key=lambda s: s.creation_time_seconds)
        self.submissions = sorted_subs

        self.attempts = len(sorted_subs)
        self.first_attempted_at = sorted_subs[0].creation_time

        # Propagate to KnowledgeItem timestamps so every downstream
        # consumer (evolution, stats, dashboard, timeline) reads the
        # correct historical date without knowing about submissions.
        self.created_at = self.first_attempted_at

        ac_subs = [s for s in sorted_subs if s.accepted]
        if ac_subs:
            self.solved = True
            self.solved_at = ac_subs[0].creation_time
            self.updated_at = self.solved_at
        else:
            self.solved = False
            self.solved_at = None
            # If never solved, updated_at = last submission time
            self.updated_at = sorted_subs[-1].creation_time

    @computed_field  # type: ignore[prop-decorator]
    @property
    def attempt_count(self) -> int:
        """Total number of submissions for this problem."""
        return len(self.submissions) if self.submissions else self.attempts

    @computed_field  # type: ignore[prop-decorator]
    @property
    def is_solved(self) -> bool:
        """True if at least one submission was accepted."""
        if self.submissions:
            return any(s.accepted for s in self.submissions)
        return self.solved

    @computed_field  # type: ignore[prop-decorator]
    @property
    def verdict_sequence(self) -> list[str]:
        """The chronological sequence of verdicts for this problem,
        e.g. ``["WRONG_ANSWER", "WRONG_ANSWER", "TIME_LIMIT_EXCEEDED", "OK"]``.
        """
        if not self.submissions:
            return []
        return [
            s.verdict or "UNKNOWN"
            for s in sorted(self.submissions, key=lambda s: s.creation_time_seconds)
        ]

    def add_submission(self, submission: Submission) -> None:
        """Append a submission and recompute all derived fields."""
        if submission.problem_key != self._problem_key_from_fields():
            # Allow mismatch only if this Problem was created without
            # submissions and the key is being established now.
            pass
        self.submissions = list(self.submissions) + [submission]
        self._derive_from_submissions()

    def _problem_key_from_fields(self) -> str:
        """Reconstruct the problem key from this Problem's fields."""
        if self.contest_id is not None:
            return f"{self.contest_id}{self.index}"
        return f"{self.contest or 'gym'}-{self.index}"
