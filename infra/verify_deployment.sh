#!/usr/bin/env bash
set -euo pipefail

: "${GOOGLE_CLOUD_PROJECT:?Set GOOGLE_CLOUD_PROJECT}"
PAIRPILOT_REGION="${PAIRPILOT_REGION:-europe-west2}"
GCLOUD="${GCLOUD:-gcloud}"
PAIRPILOT_PUBLIC_URL="${PAIRPILOT_PUBLIC_URL:-$("${GCLOUD}" run services describe pairpilot-orchestrator --project "${GOOGLE_CLOUD_PROJECT}" --region "${PAIRPILOT_REGION}" --format 'value(status.url)')}"

curl --fail --silent --show-error --connect-timeout 10 --max-time 60 \
  --retry 2 --retry-all-errors \
  "${PAIRPILOT_PUBLIC_URL}/api/health" \
  | python3 -m json.tool
curl --fail --silent --show-error --connect-timeout 10 --max-time 60 \
  --retry 2 --retry-all-errors \
  "${PAIRPILOT_PUBLIC_URL}/api/demo/state" \
  | python3 -c 'import json,sys; d=json.load(sys.stdin); assert "agent_private_profiles" not in d; print({"status": (d.get("run") or {}).get("status"), "turns": len(d["turns"]), "matches": len(d["matches"])})'
curl --fail --silent --show-error --connect-timeout 10 --max-time 60 \
  --retry 2 --retry-all-errors --output /dev/null \
  "${PAIRPILOT_PUBLIC_URL}/og.png"

"${GCLOUD}" run services describe pairpilot-orchestrator \
  --project "${GOOGLE_CLOUD_PROJECT}" --region "${PAIRPILOT_REGION}" \
  --format 'table(status.latestReadyRevisionName,status.traffic[0].percent,status.url)'
"${GCLOUD}" run services describe pairpilot-peer-agents \
  --project "${GOOGLE_CLOUD_PROJECT}" --region "${PAIRPILOT_REGION}" \
  --format 'table(status.latestReadyRevisionName,status.traffic[0].percent,status.url)'

echo "Deployment verification passed. A live run and human approval remain explicit operations."
