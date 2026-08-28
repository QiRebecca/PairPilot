"""Interactive effect-contract approval and atomic match commit."""

from __future__ import annotations

import argparse
import asyncio
import json

from pairpilot_orchestrator.config import Settings
from pairpilot_orchestrator.domain import (
    commit_approved_match,
    create_human_approval,
)
from pairpilot_orchestrator.infrastructure import GoogleCloudStore


async def approve_and_commit(
    *, run_id: str, proposal_id: str, proposal_version: int
) -> dict[str, object]:
    """Show the current effect contract and require exact explicit confirmation."""

    settings = Settings.from_environment()
    store = GoogleCloudStore(project_id=settings.project_id)
    request_id = f"{proposal_id}-v{proposal_version}"
    request = await store.get("approval_requests", request_id)
    if request is None or request.get("runId") != run_id:
        raise ValueError("approval request not found for this run")
    visible_fields = (
        "candidateIdentitySummary",
        "sharedDates",
        "soloDates",
        "costDifferenceUsd",
        "delegatedMaximumUsd",
        "agreedTerms",
        "remainingUncertainty",
        "recommendation",
        "informationDisclosed",
        "informationRemainingPrivate",
        "proposalId",
        "proposalVersion",
        "holdExpiresAt",
        "currentAvailabilityStatus",
    )
    contract = {field: request[field] for field in visible_fields}
    print(json.dumps({"effect_contract": contract}, indent=2))
    required = f"APPROVE VERSION {proposal_version}"
    prompt = (
        f"Type {required!r} to authorize this exact effect, "
        "or anything else to cancel: "
    )
    confirmation = await asyncio.to_thread(input, prompt)
    if confirmation.strip() != required:
        return {"status": "CANCELLED", "committed": False}
    disclosure_hash = str(request["disclosureHash"])
    approval = await create_human_approval(
        store=store,
        run_id=run_id,
        proposal_id=proposal_id,
        proposal_version=proposal_version,
        disclosure_hash=disclosure_hash,
    )
    match = await commit_approved_match(
        store=store,
        run_id=run_id,
        proposal_id=proposal_id,
    )
    return {
        "status": "COMMITTED",
        "committed": True,
        "approval_id": approval["approvalId"],
        "match": match,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--proposal-id", required=True)
    parser.add_argument("--proposal-version", required=True, type=int)
    args = parser.parse_args()
    result = asyncio.run(
        approve_and_commit(
            run_id=args.run_id,
            proposal_id=args.proposal_id,
            proposal_version=args.proposal_version,
        )
    )
    print(json.dumps(result, indent=2, default=str))


if __name__ == "__main__":
    main()
