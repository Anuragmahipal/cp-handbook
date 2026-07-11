"""Codeforces -> handbook mapping helpers.

Every function here is a small, pure, mechanical lookup or arithmetic
transform -- deliberately so. This prototype does not do AI reasoning
about a solution; anything that would require actually understanding a
problem (its core idea, complexity, the trick that made it click) is
left blank for a human to fill in later (see
:mod:`handbook.sync.revision_note`). What *is* mechanically derivable
from Codeforces' own metadata -- difficulty from rating, how a problem
was attempted, a human-readable name for a tag -- is derived here.
"""

from __future__ import annotations

from handbook.models import Problem
from handbook.models.enums import Difficulty, Platform, ProblemSource
from handbook.sync.codeforces import CFSubmission

# -- difficulty ---------------------------------------------------------

_DIFFICULTY_BY_RATING_CEILING: list[tuple[int, Difficulty]] = [
    (1200, Difficulty.TRIVIAL),
    (1400, Difficulty.EASY),
    (1800, Difficulty.MEDIUM),
    (2200, Difficulty.HARD),
    (2700, Difficulty.VERY_HARD),
]
"""Each entry is (exclusive rating ceiling, Difficulty). Anything at or
above the last ceiling is Difficulty.EXPERT. These thresholds are a
simple, documented convention, not a claim about "true" difficulty --
easy to retune in one place if they don't match how ratings feel in
practice.
"""


def difficulty_from_rating(rating: int | None) -> Difficulty | None:
    """Bucket a Codeforces problem rating into a :class:`Difficulty`.

    Returns ``None`` for unrated problems, same as Codeforces itself
    reports no rating for them.
    """
    if rating is None:
        return None
    for ceiling, difficulty in _DIFFICULTY_BY_RATING_CEILING:
        if rating < ceiling:
            return difficulty
    return Difficulty.EXPERT


# -- how the problem was attempted --------------------------------------

_SOURCE_BY_PARTICIPANT_TYPE: dict[str, ProblemSource] = {
    "CONTESTANT": ProblemSource.CONTEST,
    "PRACTICE": ProblemSource.PRACTICE,
    "VIRTUAL": ProblemSource.VIRTUAL_CONTEST,
    "OUT_OF_COMPETITION": ProblemSource.UPSOLVE,
    "MANAGER": ProblemSource.OTHER,
}


def source_from_participant_type(participant_type: str | None) -> ProblemSource:
    """Map Codeforces' ``author.participantType`` to a :class:`ProblemSource`.

    Falls back to :attr:`ProblemSource.OTHER` for anything unrecognized
    (including ``None``), rather than guessing.
    """
    return _SOURCE_BY_PARTICIPANT_TYPE.get(participant_type or "", ProblemSource.OTHER)


# -- time spent -----------------------------------------------------------

_MAX_SANE_RELATIVE_SECONDS = 10_000_000
"""~115 days. Codeforces uses a large sentinel value (2^31 - 1) for
``relativeTimeSeconds`` on submissions that aren't tied to a running
contest clock (plain practice, upsolving well after the fact). Treating
anything past this bound as "not a real contest timing" avoids reporting
a nonsense multi-year "time spent"."""


def time_spent_minutes(relative_time_seconds: int | None) -> int | None:
    """Minutes from contest start to submission, or ``None`` if not meaningful."""
    if relative_time_seconds is None:
        return None
    if not (0 <= relative_time_seconds < _MAX_SANE_RELATIVE_SECONDS):
        return None
    return relative_time_seconds // 60


# -- tag -> topic name -----------------------------------------------------

_TAG_TOPIC_NAMES: dict[str, str] = {
    "2-sat": "2-SAT",
    "binary search": "Binary Search",
    "bitmasks": "Bit Manipulation",
    "brute force": "Brute Force",
    "chinese remainder theorem": "Chinese Remainder Theorem",
    "combinatorics": "Combinatorics",
    "constructive algorithms": "Constructive Algorithms",
    "data structures": "Data Structures",
    "dfs and similar": "DFS",
    "divide and conquer": "Divide and Conquer",
    "dp": "Dynamic Programming",
    "dsu": "Disjoint Set Union",
    "expression parsing": "Expression Parsing",
    "fft": "Fast Fourier Transform",
    "flows": "Flows",
    "games": "Game Theory",
    "geometry": "Geometry",
    "graph matchings": "Graph Matchings",
    "graphs": "Graph Theory",
    "greedy": "Greedy",
    "hashing": "Hashing",
    "implementation": "Implementation",
    "interactive": "Interactive Problems",
    "math": "Math",
    "matrices": "Matrices",
    "meet-in-the-middle": "Meet in the Middle",
    "number theory": "Number Theory",
    "probabilities": "Probability",
    "shortest paths": "Shortest Paths",
    "sortings": "Sorting",
    "string suffix structures": "Suffix Structures",
    "strings": "String Algorithms",
    "ternary search": "Ternary Search",
    "trees": "Trees",
    "two pointers": "Two Pointers",
}
"""Codeforces' own tag vocabulary -> a human-readable topic name.

Deliberately a plain lookup table, not a fuzzy or learned mapping:
every entry is a Codeforces tag exactly as the API returns it. Anything
not in this table falls back to a title-cased version of the raw tag
(see :func:`topic_name_for_tag`) rather than being dropped, so an
unfamiliar or newly-added Codeforces tag still produces *something*
reasonable.
"""


def topic_name_for_tag(tag: str) -> str:
    """A human-readable topic name for a raw Codeforces tag.

    Used to populate ``Problem.algorithms`` -- see
    :func:`handbook.sync.mapping.build_problem_item`. These names
    deliberately don't need to match an existing Algorithm/Pattern note
    to be useful: if one doesn't exist yet, the graph layer represents
    it as a shadow node (see ``handbook.graph``), which is exactly what
    lets several synced problems that share a tag show up as connected
    once a real note for that topic is eventually added.
    """
    cleaned = tag.strip().lower()
    return _TAG_TOPIC_NAMES.get(cleaned, cleaned.title())


# -- the Problem KnowledgeItem itself -------------------------------------


def build_problem_item(
    submission: CFSubmission, *, prior_wrong_attempts: int
) -> Problem:
    """Build a ``Problem`` KnowledgeItem from one accepted submission.

    ``prior_wrong_attempts`` is the count of non-``OK`` submissions for
    this same problem, made before this one -- computed by the caller
    (see :mod:`handbook.sync.pipeline`), since it requires looking
    across *all* of a handle's submissions, not just this one.
    """
    problem = submission.problem
    contest_id_str = str(problem.contest_id) if problem.contest_id is not None else None
    contest_name = (
        contest_id_str
        if contest_id_str is not None
        else (problem.problemset_name or "gym")
    )

    return Problem(
        title=problem.name,
        platform=Platform.CODEFORCES,
        contest=contest_name,
        index=problem.index,
        contest_id=contest_id_str,
        url=problem.url,
        rating=problem.rating,
        difficulty=difficulty_from_rating(problem.rating),
        source=source_from_participant_type(submission.participant_type),
        tags=list(problem.tags),
        algorithms=[topic_name_for_tag(tag) for tag in problem.tags],
        solved=True,
        attempts=prior_wrong_attempts + 1,
        time_spent_minutes=(
            time_spent_minutes(submission.relative_time_seconds)
            if problem.contest_id is not None
            else None
        ),
    )
