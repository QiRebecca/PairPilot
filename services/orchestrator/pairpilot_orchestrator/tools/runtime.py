"""Small deterministic tool used by the live ADK verification gate."""


def verify_runtime_identity(component: str) -> dict[str, str]:
    """Return a marker proving the named Google ADK runtime is active."""

    return {
        "component": component,
        "status": "verified",
        "runtime": "google-adk-2.8.0",
    }

