"""Fail-closed runtime configuration."""

import os
from dataclasses import dataclass


LIVE_MODE = "LIVE GEMINI + GOOGLE ADK + A2A"
DEVELOPMENT_MODE = "DETERMINISTIC DEVELOPMENT FALLBACK"


@dataclass(frozen=True)
class Settings:
    """Non-secret settings shared by local ADC and Cloud Run identity auth."""

    project_id: str
    model_id: str = "gemini-3.7-flash"
    model_location: str = "global"
    execution_mode: str = LIVE_MODE

    @classmethod
    def from_environment(cls) -> "Settings":
        project_id = os.environ.get("GOOGLE_CLOUD_PROJECT", "").strip()
        if not project_id:
            raise RuntimeError("GOOGLE_CLOUD_PROJECT is required")

        mode = os.environ.get("PAIRPILOT_EXECUTION_MODE", LIVE_MODE)
        if mode not in {LIVE_MODE, DEVELOPMENT_MODE}:
            raise RuntimeError(f"Unsupported execution mode: {mode}")

        model_id = os.environ.get(
            "PAIRPILOT_MODEL_ID", "gemini-3.7-flash"
        )
        if mode == LIVE_MODE and model_id != "gemini-3.7-flash":
            raise RuntimeError(
                "Live judging mode is pinned to verified gemini-3.7-flash"
            )

        return cls(
            project_id=project_id,
            model_id=model_id,
            model_location=os.environ.get("GOOGLE_CLOUD_LOCATION", "global"),
            execution_mode=mode,
        )

