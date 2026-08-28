"""Cloud Run entry point for independent A2A peer agents."""

import os

from pairpilot_peer_agents.a2a_server import create_app


def required_environment(name: str) -> str:
    """Return a required non-secret setting or fail startup."""

    value = os.environ.get(name, "").strip()
    if not value:
        raise RuntimeError(f"{name} is required")
    return value


app = create_app(
    base_url=os.environ.get("PAIRPILOT_PUBLIC_BASE_URL", "http://localhost:8080"),
    project_id=required_environment("GOOGLE_CLOUD_PROJECT"),
    model_id=os.environ.get("PAIRPILOT_MODEL_ID", "gemini-3.7-flash"),
    location=os.environ.get("GOOGLE_CLOUD_LOCATION", "global"),
    persist_to_firestore=os.environ.get(
        "PAIRPILOT_PERSIST_PROVENANCE", "true"
    ).lower()
    == "true",
)

