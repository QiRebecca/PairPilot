"""Fail-closed runtime configuration."""

import os
import re
from dataclasses import dataclass

LIVE_MODE = "LIVE GEMINI + GOOGLE ADK + A2A"
DEVELOPMENT_MODE = "DETERMINISTIC DEVELOPMENT FALLBACK"
ENVIRONMENT_PATTERN = re.compile(r"^[a-z][a-z0-9_-]{0,31}$")
PREFIX_PATTERN = re.compile(r"^[a-z][a-z0-9_]{0,39}_$")


def runtime_environment() -> str:
    value = os.environ.get("PAIRPILOT_ENVIRONMENT", "production").strip()
    if not ENVIRONMENT_PATTERN.fullmatch(value):
        raise RuntimeError("PAIRPILOT_ENVIRONMENT is invalid")
    return value


@dataclass(frozen=True)
class Settings:
    """Non-secret settings shared by local ADC and Cloud Run identity auth."""

    project_id: str
    model_id: str = "gemini-3.7-flash"
    model_location: str = "global"
    execution_mode: str = LIVE_MODE
    environment: str = "production"
    collection_prefix: str = ""
    event_topic_id: str = "pairpilot-events"

    @classmethod
    def from_environment(cls) -> "Settings":
        project_id = os.environ.get("GOOGLE_CLOUD_PROJECT", "").strip()
        if not project_id:
            raise RuntimeError("GOOGLE_CLOUD_PROJECT is required")

        mode = os.environ.get("PAIRPILOT_EXECUTION_MODE", LIVE_MODE)
        if mode not in {LIVE_MODE, DEVELOPMENT_MODE}:
            raise RuntimeError(f"Unsupported execution mode: {mode}")

        model_id = os.environ.get("PAIRPILOT_MODEL_ID", "gemini-3.7-flash")
        if mode == LIVE_MODE and model_id != "gemini-3.7-flash":
            raise RuntimeError(
                "Live judging mode is pinned to verified gemini-3.7-flash"
            )

        environment = runtime_environment()
        collection_prefix = os.environ.get("PAIRPILOT_COLLECTION_PREFIX", "").strip()
        if collection_prefix and not PREFIX_PATTERN.fullmatch(collection_prefix):
            raise RuntimeError("PAIRPILOT_COLLECTION_PREFIX is invalid")
        if environment != "production" and not collection_prefix:
            raise RuntimeError(
                "non-production environments require PAIRPILOT_COLLECTION_PREFIX"
            )
        event_topic_id = os.environ.get("PAIRPILOT_EVENT_TOPIC_ID", "pairpilot-events")
        if not ENVIRONMENT_PATTERN.fullmatch(event_topic_id):
            raise RuntimeError("PAIRPILOT_EVENT_TOPIC_ID is invalid")
        return cls(
            project_id=project_id,
            model_id=model_id,
            model_location=os.environ.get("GOOGLE_CLOUD_LOCATION", "global"),
            execution_mode=mode,
            environment=environment,
            collection_prefix=collection_prefix,
            event_topic_id=event_topic_id,
        )
