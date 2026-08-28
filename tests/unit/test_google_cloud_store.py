from datetime import UTC, date, datetime

from pairpilot_orchestrator.infrastructure.google_cloud import (
    decode_fields,
    encode_fields,
)


def test_firestore_codec_round_trip_for_authoritative_shapes() -> None:
    value = {
        "active": True,
        "version": 2,
        "confidence": 0.78,
        "date": date(2026, 7, 7),
        "created": datetime(2026, 8, 28, 12, 0, tzinfo=UTC),
        "terms": ["equal split", "quiet overnight"],
        "scope": {"agent": "qi-agent", "private": False},
        "none": None,
    }
    decoded = decode_fields(encode_fields(value))
    assert decoded["active"] is True
    assert decoded["version"] == 2
    assert decoded["confidence"] == 0.78
    assert decoded["date"] == "2026-07-07"
    assert decoded["created"] == "2026-08-28T12:00:00Z"
    assert decoded["terms"] == ["equal split", "quiet overnight"]
    assert decoded["scope"] == {"agent": "qi-agent", "private": False}
    assert decoded["none"] is None
