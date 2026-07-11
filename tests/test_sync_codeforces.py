"""Tests for CodeforcesClient: parsing the public Codeforces API."""

from __future__ import annotations

import json

import pytest

from handbook.sync.codeforces import (
    CFProblem,
    CodeforcesAPIError,
    CodeforcesClient,
    CodeforcesTransportError,
)


def _transport_returning(payload: dict):
    def _transport(url: str) -> bytes:
        return json.dumps(payload).encode()

    return _transport


def test_fetch_submissions_parses_a_full_submission(cf_submission_payload):
    payload = {"status": "OK", "result": [cf_submission_payload(id=1)]}
    client = CodeforcesClient(transport=_transport_returning(payload))

    submissions = client.fetch_submissions("someone")

    assert len(submissions) == 1
    submission = submissions[0]
    assert submission.id == 1
    assert submission.contest_id == 1000
    assert submission.verdict == "OK"
    assert submission.accepted is True
    assert submission.participant_type == "CONTESTANT"
    assert submission.problem.name == "Sample Problem"
    assert submission.problem.rating == 1200
    assert submission.problem.tags == ("implementation",)


def test_accepted_is_false_for_non_ok_verdicts(cf_submission_payload):
    payload = {
        "status": "OK",
        "result": [cf_submission_payload(id=1, verdict="WRONG_ANSWER")],
    }
    client = CodeforcesClient(transport=_transport_returning(payload))

    submission = client.fetch_submissions("someone")[0]

    assert submission.accepted is False


def test_missing_verdict_is_not_accepted(cf_submission_payload):
    payload = {"status": "OK", "result": [cf_submission_payload(id=1, verdict=None)]}
    client = CodeforcesClient(transport=_transport_returning(payload))

    submission = client.fetch_submissions("someone")[0]

    assert submission.verdict is None
    assert submission.accepted is False


def test_request_url_includes_handle_from_and_count(cf_submission_payload):
    payload = {"status": "OK", "result": []}
    seen_urls: list[str] = []

    def _transport(url: str) -> bytes:
        seen_urls.append(url)
        return json.dumps(payload).encode()

    client = CodeforcesClient(transport=_transport)
    client.fetch_submissions("tourist", count=50, from_index=5)

    assert len(seen_urls) == 1
    assert "handle=tourist" in seen_urls[0]
    assert "count=50" in seen_urls[0]
    assert "from=5" in seen_urls[0]
    assert seen_urls[0].startswith("https://codeforces.com/api/user.status?")


def test_api_failure_status_raises_codeforces_api_error():
    payload = {"status": "FAILED", "comment": "handle: User not found: someone"}
    client = CodeforcesClient(transport=_transport_returning(payload))

    with pytest.raises(CodeforcesAPIError, match="User not found"):
        client.fetch_submissions("someone")


def test_api_failure_without_comment_still_raises():
    payload = {"status": "FAILED"}
    client = CodeforcesClient(transport=_transport_returning(payload))

    with pytest.raises(CodeforcesAPIError):
        client.fetch_submissions("someone")


def test_transport_error_propagates():
    def _broken_transport(url: str) -> bytes:
        raise CodeforcesTransportError("boom")

    client = CodeforcesClient(transport=_broken_transport)

    with pytest.raises(CodeforcesTransportError):
        client.fetch_submissions("someone")


# -- CFProblem -----------------------------------------------------------


def test_problem_key_uses_contest_id_and_index():
    problem = CFProblem(
        contest_id=1868,
        problemset_name=None,
        index="A",
        name="X",
        type="PROGRAMMING",
        rating=None,
        tags=(),
    )

    assert problem.problem_key == "1868A"


def test_problem_key_falls_back_for_gym_problems_without_contest_id():
    problem = CFProblem(
        contest_id=None,
        problemset_name="acmsguru",
        index="101",
        name="X",
        type="PROGRAMMING",
        rating=None,
        tags=(),
    )

    assert problem.problem_key == "acmsguru-101"


def test_problem_url_built_from_contest_id_and_index():
    problem = CFProblem(
        contest_id=1868,
        problemset_name=None,
        index="A",
        name="X",
        type="PROGRAMMING",
        rating=None,
        tags=(),
    )

    assert problem.url == "https://codeforces.com/contest/1868/problem/A"


def test_problem_url_is_blank_without_a_contest_id():
    problem = CFProblem(
        contest_id=None,
        problemset_name="acmsguru",
        index="101",
        name="X",
        type="PROGRAMMING",
        rating=None,
        tags=(),
    )

    assert problem.url == ""
