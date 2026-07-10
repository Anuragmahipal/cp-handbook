"""Strongly typed enumerations shared across knowledge models.

Every enum here is a :class:`_LenientStrEnum`: a plain ``str`` enum that
also accepts case-insensitive matches and a small set of common
shorthand aliases (``"cf"`` -> ``Platform.CODEFORCES``) during Pydantic
validation. This keeps construction ergonomic for humans and AI agents
alike -- callers don't need to know the exact canonical spelling -- while
every stored object still ends up with a single, canonical, typed value
instead of a free-form string. That's what makes these safe to branch on
later (search, graph, recommendations) without re-normalizing string
data at every call site.
"""

from __future__ import annotations

from enum import StrEnum


class _LenientStrEnum(StrEnum):
    """Base class for every enum in this module. Not used directly."""

    @classmethod
    def _missing_(cls, value: object) -> _LenientStrEnum | None:
        if not isinstance(value, str):
            return None
        normalized = value.strip().lower()
        for member in cls:
            if member.value.lower() == normalized:
                return member
        target = cls._aliases().get(normalized)
        if target is not None:
            return cls(target)
        return None

    @classmethod
    def _aliases(cls) -> dict[str, str]:
        """Mapping of lowercase shorthand -> canonical enum value.

        Overridden per-enum. A plain classmethod (not a class attribute)
        so the Enum metaclass never mistakes it for a member.
        """
        return {}


class Difficulty(_LenientStrEnum):
    """Subjective or platform-reported difficulty of a piece of knowledge."""

    TRIVIAL = "Trivial"
    EASY = "Easy"
    MEDIUM = "Medium"
    HARD = "Hard"
    VERY_HARD = "Very Hard"
    EXPERT = "Expert"


class KnowledgeStatus(_LenientStrEnum):
    """Where an item stands in Anurag's learning/review lifecycle."""

    ACTIVE = "Active"
    LEARNING = "Learning"
    NEEDS_REVIEW = "Needs Review"
    MASTERED = "Mastered"
    ARCHIVED = "Archived"


class Platform(_LenientStrEnum):
    """A competitive-programming judge, platform, or contest organizer."""

    CODEFORCES = "Codeforces"
    LEETCODE = "LeetCode"
    ATCODER = "AtCoder"
    CODECHEF = "CodeChef"
    CSES = "CSES"
    ICPC = "ICPC"
    IOI = "IOI"
    HACKERRANK = "HackerRank"
    SPOJ = "SPOJ"
    USACO = "USACO"
    TOPCODER = "TopCoder"
    OTHER = "Other"

    @classmethod
    def _aliases(cls) -> dict[str, str]:
        return {
            "cf": "Codeforces",
            "lc": "LeetCode",
            "leet code": "LeetCode",
            "ac": "AtCoder",
            "at coder": "AtCoder",
            "cc": "CodeChef",
            "code chef": "CodeChef",
            "hr": "HackerRank",
            "hacker rank": "HackerRank",
            "tc": "TopCoder",
            "top coder": "TopCoder",
        }


class ProblemSource(_LenientStrEnum):
    """How a problem was encountered."""

    CONTEST = "Contest"
    PRACTICE = "Practice"
    VIRTUAL_CONTEST = "Virtual Contest"
    MOCK_INTERVIEW = "Mock Interview"
    UPSOLVE = "Upsolve"
    RECOMMENDATION = "Recommendation"
    OTHER = "Other"


class ContestType(_LenientStrEnum):
    """The format/stakes of a contest."""

    RATED = "Rated"
    UNRATED = "Unrated"
    VIRTUAL = "Virtual"
    MOCK = "Mock"
    ONSITE = "Onsite"
    EDUCATIONAL = "Educational"
    OTHER = "Other"


class PatternCategory(_LenientStrEnum):
    """A broad CP subject area.

    Shared by :class:`~handbook.models.pattern.Pattern` (what kind of
    pattern this is), :class:`~handbook.models.algorithm.Algorithm`
    (what family a technique belongs to), and
    :class:`~handbook.models.topic.Topic` (the area a topic hub covers)
    -- one taxonomy, reused, instead of three overlapping ones.
    """

    GREEDY = "Greedy"
    DYNAMIC_PROGRAMMING = "Dynamic Programming"
    GRAPH = "Graph"
    TREE = "Tree"
    STRING = "String"
    MATH = "Math"
    NUMBER_THEORY = "Number Theory"
    COMBINATORICS = "Combinatorics"
    DATA_STRUCTURE = "Data Structure"
    GEOMETRY = "Geometry"
    SEARCH = "Search"
    TWO_POINTERS = "Two Pointers"
    DIVIDE_AND_CONQUER = "Divide and Conquer"
    BIT_MANIPULATION = "Bit Manipulation"
    OTHER = "Other"

    @classmethod
    def _aliases(cls) -> dict[str, str]:
        return {
            "dp": "Dynamic Programming",
            "graphs": "Graph",
            "trees": "Tree",
            "strings": "String",
            "geometry / math": "Geometry",
            "bitmask": "Bit Manipulation",
        }


class MistakeCategory(_LenientStrEnum):
    """The nature of a recurring mistake."""

    LOGIC_ERROR = "Logic Error"
    EDGE_CASE = "Edge Case"
    OFF_BY_ONE = "Off By One"
    TIME_LIMIT_EXCEEDED = "Time Limit Exceeded"
    INTEGER_OVERFLOW = "Integer Overflow"
    WRONG_ALGORITHM_CHOICE = "Wrong Algorithm Choice"
    IMPLEMENTATION_BUG = "Implementation Bug"
    MISREAD_PROBLEM = "Misread Problem"
    PRECISION = "Precision / Floating Point"
    RUNTIME_ERROR = "Runtime Error"
    OTHER = "Other"

    @classmethod
    def _aliases(cls) -> dict[str, str]:
        return {
            "tle": "Time Limit Exceeded",
            "overflow": "Integer Overflow",
            "off-by-one": "Off By One",
            "re": "Runtime Error",
        }


class RelationType(_LenientStrEnum):
    """The semantics of an edge between two knowledge items.

    Kept intentionally generic and reusable across every model rather
    than inventing a bespoke enum per relationship field -- a future
    graph layer only ever has to understand this one vocabulary.
    """

    PREREQUISITE = "prerequisite"
    """Target must be understood before this item."""

    USES = "uses"
    """This item relies on target as a building block."""

    USED_IN = "used_in"
    """Inverse of USES: this item is a building block of target."""

    APPEARS_IN = "appears_in"
    """This item (e.g. an algorithm or pattern) shows up in target
    (typically a Problem or Contest)."""

    CONTAINS = "contains"
    """Target is a member/child of this item (e.g. Contest -> Problem,
    Topic -> Algorithm)."""

    PART_OF = "part_of"
    """Inverse of CONTAINS."""

    GENERALIZES = "generalizes"
    SPECIALIZES = "specializes"
    VARIANT_OF = "variant_of"
    SIMILAR_TO = "similar_to"
    CONTRASTS_WITH = "contrasts_with"
    RELATED = "related"
    """Generic fallback when no more specific relation applies."""
