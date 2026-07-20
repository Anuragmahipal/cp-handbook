"""Codeforces API client: fetches submissions via the public API.

Talks to ``https://codeforces.com/api/{method}`` over a plain HTTP GET --
no API key is needed for the read-only, per-user endpoint this package
uses (``user.status``). The actual HTTP call is a single injectable
:data:`Transport` function, so tests exercise the full parsing logic
against a canned response with zero real network access -- see
``tests/test_sync_codeforces.py``.
"""

from __future__ import annotations

import json
import urllib.request
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from urllib.parse import urlencode

_BASE_URL = "https://codeforces.com/api"
_USER_AGENT = "cp-handbook-sync/0.1"


class CodeforcesError(Exception):
    """Base class for every error this client raises."""


class CodeforcesAPIError(CodeforcesError):
    """The API responded, but with ``{"status": "FAILED", ...}``.

    Covers things like an unknown handle -- the request reached
    Codeforces fine, Codeforces just said no.
    """


class CodeforcesTransportError(CodeforcesError):
    """The HTTP request itself failed: network, timeout, DNS, etc."""


Transport = Callable[[str], bytes]
"""A function from a fully-built request URL to the raw response body.

The seam this client is built around: production code never sees
anything but :func:`_default_transport`, while tests supply a fake that
returns canned JSON bytes for a given URL -- no real network access,
and no need to monkeypatch ``urllib`` globally.
"""


def _default_transport(url: str) -> bytes:
    request = urllib.request.Request(url, headers={"User-Agent": _USER_AGENT})
    try:
        with urllib.request.urlopen(request, timeout=15) as response:  # noqa: S310
            return response.read()
    except OSError as exc:
        raise CodeforcesTransportError(f"Request to {url} failed: {exc}") from exc


@dataclass(frozen=True, slots=True)
class CFProblem:
    """A Codeforces ``Problem`` object, as embedded in a submission.

    See https://codeforces.com/apiHelp/objects#Problem.
    """

    contest_id: int | None
    problemset_name: str | None
    index: str
    name: str
    type: str
    rating: int | None
    tags: tuple[str, ...]

    @property
    def problem_key(self) -> str:
        """A stable identity for this problem, e.g. ``"1868A"``.

        Falls back to the problemset name for gym/problemset-only
        problems that have no ``contest_id``, so every problem still
        gets a usable dedup key.
        """
        if self.contest_id is not None:
            return f"{self.contest_id}{self.index}"
        return f"{self.problemset_name or 'gym'}-{self.index}"

    @property
    def url(self) -> str:
        """The problem's page on codeforces.com, or ``""`` if it has no contest."""
        if self.contest_id is None:
            return ""
        return f"https://codeforces.com/contest/{self.contest_id}/problem/{self.index}"


@dataclass(frozen=True, slots=True)
class CFSubmission:
    """A Codeforces ``Submission`` object: one judged attempt at a problem.

    See https://codeforces.com/apiHelp/objects#Submission. Only the
    fields this package actually uses are kept -- ``author`` is
    flattened down to just ``participant_type``.
    """

    id: int
    contest_id: int | None
    creation_time: datetime
    creation_time_seconds: int
    """Unix timestamp (seconds since epoch) when the submission was created.
    Stored alongside ``creation_time`` so the domain layer can use
    the raw integer for deterministic sorting and id generation."""
    relative_time_seconds: int | None
    problem: CFProblem
    verdict: str | None
    participant_type: str | None
    programming_language: str
    time_consumed_ms: int
    """Time consumed by the solution in milliseconds."""
    memory_consumed_bytes: int
    """Memory consumed by the solution in bytes."""
    passed_test_count: int
    """Number of tests passed before the verdict was reached."""

    @property
    def accepted(self) -> bool:
        return self.verdict == "OK"


class CodeforcesClient:
    """Minimal read-only client for the public Codeforces API."""

    def __init__(
        self, *, transport: Transport | None = None, base_url: str = _BASE_URL
    ) -> None:
        self._transport = transport or _default_transport
        self._base_url = base_url

    def fetch_submissions(
        self, handle: str, *, count: int = 10_000, from_index: int = 1
    ) -> list[CFSubmission]:
        """Every submission by ``handle`` (any verdict), newest first.

        This is the one call the whole sync pipeline is built on:
        fetching everything (not just accepted submissions) lets the
        pipeline also count failed attempts before an eventual AC,
        without a second round-trip.

        Raises:
            CodeforcesAPIError: if the API reports failure (e.g. an
                unknown handle).
            CodeforcesTransportError: if the HTTP request fails outright.
        """
        query = urlencode({"handle": handle, "from": from_index, "count": count})
        url = f"{self._base_url}/user.status?{query}"
        raw = self._transport(url)
        payload = json.loads(raw)
        if payload.get("status") != "OK":
            raise CodeforcesAPIError(
                payload.get("comment") or "Codeforces API request failed."
            )
        return [self._parse_submission(item) for item in payload["result"]]

    @staticmethod
    def _parse_problem(data: dict) -> CFProblem:
        return CFProblem(
            contest_id=data.get("contestId"),
            problemset_name=data.get("problemsetName"),
            index=data["index"],
            name=data["name"],
            type=data.get("type", "PROGRAMMING"),
            rating=data.get("rating"),
            tags=tuple(data.get("tags", ())),
        )

    @classmethod
    def _parse_submission(cls, data: dict) -> CFSubmission:
        author = data.get("author") or {}
        return CFSubmission(
            id=data["id"],
            contest_id=data.get("contestId"),
            creation_time=datetime.fromtimestamp(data["creationTimeSeconds"]),
            creation_time_seconds=data["creationTimeSeconds"],
            relative_time_seconds=data.get("relativeTimeSeconds"),
            problem=cls._parse_problem(data["problem"]),
            verdict=data.get("verdict"),
            participant_type=author.get("participantType"),
            programming_language=data.get("programmingLanguage", ""),
            time_consumed_ms=data.get("timeConsumedMillis", 0),
            memory_consumed_bytes=data.get("memoryConsumedBytes", 0),
            passed_test_count=data.get("passedTestCount", 0),
        )
