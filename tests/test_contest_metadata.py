"""Tests for contest metadata fetching and storage (PR #3)."""

from __future__ import annotations

from handbook.models.enums import ContestType, Platform
from handbook.sync.codeforces import CFContest, CodeforcesClient
from handbook.sync.mapping import build_contest_item


def test_fetch_contests_parses_all_fields():
    """CFContest must parse every field from contest.list API."""
    response = {
        "status": "OK",
        "result": [{
            "id": 1868,
            "name": "Codeforces Round 900 (Div. 2)",
            "type": "CF",
            "phase": "FINISHED",
            "frozen": False,
            "durationSeconds": 7200,
            "startTimeSeconds": 1_700_000_000,
            "relativeTimeSeconds": 7200,
            "preparedBy": "tourist",
            "websiteUrl": "https://codeforces.com",
            "description": "A regular round",
            "difficulty": 2,
            "kind": "regular",
            "icpcRegion": None,
            "country": "Russia",
            "city": "Moscow",
            "season": "2024",
        }]
    }

    def _transport(url: str) -> bytes:
        import json
        return json.dumps(response).encode()

    client = CodeforcesClient(transport=_transport)
    contests = client.fetch_contests()
    assert len(contests) == 1
    c = contests[0]
    assert c.id == 1868
    assert c.name == "Codeforces Round 900 (Div. 2)"
    assert c.type == "CF"
    assert c.phase == "FINISHED"
    assert c.frozen is False
    assert c.duration_seconds == 7200
    assert c.duration_minutes == 120
    assert c.start_time_seconds == 1_700_000_000
    assert c.start_time is not None
    assert c.prepared_by == "tourist"
    assert c.website_url == "https://codeforces.com"
    assert c.description == "A regular round"
    assert c.difficulty == 2
    assert c.kind == "regular"
    assert c.country == "Russia"
    assert c.city == "Moscow"
    assert c.season == "2024"


def test_build_contest_item_maps_fields():
    """build_contest_item must create a proper Contest KnowledgeItem."""
    cf = CFContest(
        id=1868, name="Round 900", type="CF", phase="FINISHED",
        frozen=False, duration_seconds=7200, start_time_seconds=1_700_000_000,
        relative_time_seconds=None, prepared_by=None, website_url=None,
        description=None, difficulty=None, kind=None, icpc_region=None,
        country=None, city=None, season=None,
    )
    contest = build_contest_item(cf)
    assert contest.title == "Round 900"
    assert contest.platform == Platform.CODEFORCES
    assert contest.contest_type == ContestType.RATED
    assert contest.duration_minutes == 120
    assert contest.start_time is not None


def test_contest_type_mapping():
    """CF type strings must map correctly to ContestType."""
    from handbook.sync.mapping import _contest_type_from_cf
    assert _contest_type_from_cf("CF") == ContestType.RATED
    assert _contest_type_from_cf("IOI") == ContestType.UNRATED
    assert _contest_type_from_cf("ICPC") == ContestType.UNRATED
    assert _contest_type_from_cf("UNKNOWN") == ContestType.OTHER
    assert _contest_type_from_cf("") == ContestType.OTHER
