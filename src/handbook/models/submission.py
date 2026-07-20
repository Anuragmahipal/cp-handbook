"""Submission: a single competitive programming submission event.

Every submission — accepted or not — is a first-class historical record.
This model stores the raw data from Codeforces (or any future platform)
so that the knowledge layer can derive facts (attempt counts, solve times,
streaks, verdict sequences) rather than maintaining them manually.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone


@dataclass(frozen=True, slots=True)
class Submission:
    """One submission to a judge, with all metadata the platform provides."""

    id: int
    """Platform-specific submission identifier."""

    problem_key: str
    """Stable problem identifier, e.g. ``"1868A"``."""

    contest_id: int | None
    """The contest this submission was made during, if any."""

    creation_time_seconds: int
    """Unix timestamp (seconds since epoch) when the submission was created."""

    verdict: str | None
    """Platform verdict string, e.g. ``"OK"``, ``"WRONG_ANSWER"``,
    ``"TIME_LIMIT_EXCEEDED"``, ``"COMPILATION_ERROR"``, ``"SKIPPED"``,
    or ``None`` when the platform has not yet assigned a verdict."""

    programming_language: str
    """The language the solution was written in."""

    time_consumed_ms: int
    """Time consumed by the solution in milliseconds."""

    memory_consumed_bytes: int
    """Memory consumed by the solution in bytes."""

    passed_test_count: int
    """Number of tests passed before the verdict was reached."""

    @property
    def accepted(self) -> bool:
        """True iff the verdict is ``"OK"``."""
        return self.verdict == "OK"

    @property
    def creation_time(self) -> datetime:
        """The submission creation time as a timezone-aware ``datetime``."""
        return datetime.fromtimestamp(self.creation_time_seconds, tz=timezone.utc)

    def to_dict(self) -> dict:
        """Serialize to a plain dict for JSON storage."""
        return {
            "id": self.id,
            "problem_key": self.problem_key,
            "contest_id": self.contest_id,
            "creation_time_seconds": self.creation_time_seconds,
            "verdict": self.verdict,
            "programming_language": self.programming_language,
            "time_consumed_ms": self.time_consumed_ms,
            "memory_consumed_bytes": self.memory_consumed_bytes,
            "passed_test_count": self.passed_test_count,
        }

    @classmethod
    def from_dict(cls, data: dict) -> Submission:
        """Deserialize from a plain dict."""
        return cls(
            id=data["id"],
            problem_key=data["problem_key"],
            contest_id=data.get("contest_id"),
            creation_time_seconds=data["creation_time_seconds"],
            verdict=data.get("verdict"),
            programming_language=data["programming_language"],
            time_consumed_ms=data["time_consumed_ms"],
            memory_consumed_bytes=data["memory_consumed_bytes"],
            passed_test_count=data["passed_test_count"],
        )
