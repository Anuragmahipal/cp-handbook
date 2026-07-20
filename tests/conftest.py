from pathlib import Path

import pytest

from handbook import Handbook


@pytest.fixture
def vault_root(tmp_path: Path) -> Path:
    """A vault root that does not exist yet, to exercise nested creation."""
    return tmp_path / "vault"


@pytest.fixture
def hb(vault_root: Path) -> Handbook:
    return Handbook(root=vault_root)


@pytest.fixture
def cf_submission_payload():
    """Factory for a raw Codeforces ``user.status`` submission dict.

    Matches the shape documented at
    https://codeforces.com/apiHelp/objects#Submission -- used to build
    fake API responses in every ``handbook.sync`` test without a real
    network call.
    """

    def _build(
        *,
        id: int,
        contest_id: int | None = 1000,
        problemset_name: str | None = None,
        index: str = "A",
        name: str = "Sample Problem",
        rating: int | None = 1200,
        tags: tuple[str, ...] = ("implementation",),
        verdict: str | None = "OK",
        creation_time: int = 1_700_000_000,
        relative_time: int | None = 300,
        participant_type: str | None = "CONTESTANT",
        programming_language: str = "GNU C++20",
        time_consumed_ms: int = 30,
        memory_consumed_bytes: int = 1000,
        passed_test_count: int = 10,
    ) -> dict:
        return {
            "id": id,
            "contestId": contest_id,
            "creationTimeSeconds": creation_time,
            "relativeTimeSeconds": relative_time,
            "problem": {
                "contestId": contest_id,
                "problemsetName": problemset_name,
                "index": index,
                "name": name,
                "type": "PROGRAMMING",
                "rating": rating,
                "tags": list(tags),
            },
            "author": {"participantType": participant_type},
            "programmingLanguage": programming_language,
            "verdict": verdict,
            "testset": "TESTS",
            "passedTestCount": passed_test_count,
            "timeConsumedMillis": time_consumed_ms,
            "memoryConsumedBytes": memory_consumed_bytes,
        }

    return _build
