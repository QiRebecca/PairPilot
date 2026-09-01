from datetime import UTC, date, datetime

from pairpilot_orchestrator.config import Settings
from pairpilot_orchestrator.infrastructure.google_cloud import (
    GoogleCloudStore,
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


def test_candidate_collection_prefix_changes_physical_authority_boundary() -> None:
    store = GoogleCloudStore.__new__(GoogleCloudStore)
    store.project_id = "test-project"
    store.collection_prefix = "candidate_v2_"
    store._documents = "https://firestore.example/documents"
    assert store._physical_collection("users") == "candidate_v2_users"
    assert (
        store.document_name("task_workspaces", "task_one")
        == "projects/test-project/databases/(default)/documents/"
        "candidate_v2_task_workspaces/task_one"
    )


def test_nonproduction_environment_fails_closed_without_prefix(monkeypatch) -> None:
    monkeypatch.setenv("GOOGLE_CLOUD_PROJECT", "test-project")
    monkeypatch.setenv("PAIRPILOT_ENVIRONMENT", "candidate")
    monkeypatch.delenv("PAIRPILOT_COLLECTION_PREFIX", raising=False)
    try:
        Settings.from_environment()
    except RuntimeError as exc:
        assert "PAIRPILOT_COLLECTION_PREFIX" in str(exc)
    else:
        raise AssertionError("candidate environment accepted shared collections")


def test_candidate_environment_requires_and_accepts_isolated_topic(monkeypatch) -> None:
    monkeypatch.setenv("GOOGLE_CLOUD_PROJECT", "test-project")
    monkeypatch.setenv("PAIRPILOT_ENVIRONMENT", "candidate")
    monkeypatch.setenv("PAIRPILOT_COLLECTION_PREFIX", "candidate_v2_")
    monkeypatch.setenv("PAIRPILOT_EVENT_TOPIC_ID", "pairpilot-v2-candidate-events")
    settings = Settings.from_environment()
    assert settings.environment == "candidate"
    assert settings.collection_prefix == "candidate_v2_"
    assert settings.event_topic_id == "pairpilot-v2-candidate-events"
