#!/usr/bin/env bash
set -euo pipefail

: "${GOOGLE_CLOUD_PROJECT:?Set GOOGLE_CLOUD_PROJECT}"
PAIRPILOT_REGION="${PAIRPILOT_REGION:-europe-west2}"
PAIRPILOT_MODEL_ID="${PAIRPILOT_MODEL_ID:-gemini-3.7-flash}"
GCLOUD="${GCLOUD:-gcloud}"
PAIRPILOT_CANDIDATE_TAG="${PAIRPILOT_CANDIDATE_TAG:-intent-v2}"
PAIRPILOT_RUNTIME_SA="pairpilot-runtime@${GOOGLE_CLOUD_PROJECT}.iam.gserviceaccount.com"
PAIRPILOT_IMAGE_TAG="${PAIRPILOT_IMAGE_TAG:-intent-v2-$(git rev-parse --short=12 HEAD)}"
PAIRPILOT_REPOSITORY="${PAIRPILOT_REGION}-docker.pkg.dev/${GOOGLE_CLOUD_PROJECT}/pairpilot"
PAIRPILOT_PEER_IMAGE="${PAIRPILOT_REPOSITORY}/peer-agents:${PAIRPILOT_IMAGE_TAG}"
PAIRPILOT_WEB_IMAGE="${PAIRPILOT_REPOSITORY}/orchestrator:${PAIRPILOT_IMAGE_TAG}"

service_url() {
  "${GCLOUD}" run services describe "$1" \
    --project "${GOOGLE_CLOUD_PROJECT}" \
    --region "${PAIRPILOT_REGION}" \
    --format 'value(status.url)'
}

tagged_url() {
  local base_url
  base_url="$(service_url "$1")"
  printf 'https://%s---%s\n' "${PAIRPILOT_CANDIDATE_TAG}" "${base_url#https://}"
}

PAIRPILOT_PEER_TAGGED_URL="$(tagged_url pairpilot-peer-agents)"
PAIRPILOT_PUBLIC_TAGGED_URL="$(tagged_url pairpilot-orchestrator)"

"${GCLOUD}" builds submit \
  --project "${GOOGLE_CLOUD_PROJECT}" \
  --region "${PAIRPILOT_REGION}" \
  --config infra/cloudbuild-peer.yaml \
  --substitutions "_IMAGE=${PAIRPILOT_PEER_IMAGE}" .

"${GCLOUD}" run deploy pairpilot-peer-agents \
  --project "${GOOGLE_CLOUD_PROJECT}" \
  --region "${PAIRPILOT_REGION}" \
  --image "${PAIRPILOT_PEER_IMAGE}" \
  --service-account "${PAIRPILOT_RUNTIME_SA}" \
  --no-allow-unauthenticated \
  --no-traffic \
  --tag "${PAIRPILOT_CANDIDATE_TAG}" \
  --min 0 --max 1 --concurrency 4 --cpu 1 --memory 512Mi --timeout 90 \
  --set-env-vars "GOOGLE_CLOUD_PROJECT=${GOOGLE_CLOUD_PROJECT},GOOGLE_CLOUD_LOCATION=global,PAIRPILOT_MODEL_ID=${PAIRPILOT_MODEL_ID},PAIRPILOT_PERSIST_PROVENANCE=true,PAIRPILOT_PUBLIC_BASE_URL=${PAIRPILOT_PEER_TAGGED_URL}" \
  --quiet

"${GCLOUD}" run services add-iam-policy-binding pairpilot-peer-agents \
  --project "${GOOGLE_CLOUD_PROJECT}" \
  --region "${PAIRPILOT_REGION}" \
  --member "serviceAccount:${PAIRPILOT_RUNTIME_SA}" \
  --role roles/run.invoker >/dev/null

"${GCLOUD}" builds submit \
  --project "${GOOGLE_CLOUD_PROJECT}" \
  --region "${PAIRPILOT_REGION}" \
  --config infra/cloudbuild-orchestrator.yaml \
  --substitutions "_IMAGE=${PAIRPILOT_WEB_IMAGE}" .

"${GCLOUD}" run deploy pairpilot-orchestrator \
  --project "${GOOGLE_CLOUD_PROJECT}" \
  --region "${PAIRPILOT_REGION}" \
  --image "${PAIRPILOT_WEB_IMAGE}" \
  --service-account "${PAIRPILOT_RUNTIME_SA}" \
  --allow-unauthenticated \
  --no-traffic \
  --tag "${PAIRPILOT_CANDIDATE_TAG}" \
  --min 0 --max 1 --concurrency 4 --cpu 1 --memory 1Gi --timeout 120 \
  --startup-probe "httpGet.path=/api/health,httpGet.port=8080,timeoutSeconds=3,periodSeconds=5,failureThreshold=12" \
  --liveness-probe "httpGet.path=/api/health,httpGet.port=8080,initialDelaySeconds=5,timeoutSeconds=3,periodSeconds=30,failureThreshold=3" \
  --set-env-vars "GOOGLE_CLOUD_PROJECT=${GOOGLE_CLOUD_PROJECT},GOOGLE_CLOUD_LOCATION=global,PAIRPILOT_MODEL_ID=${PAIRPILOT_MODEL_ID},PAIRPILOT_PEER_BASE_URL=${PAIRPILOT_PEER_TAGGED_URL},PAIRPILOT_PUBLIC_BASE_URL=${PAIRPILOT_PUBLIC_TAGGED_URL}" \
  --quiet

printf 'Candidate orchestrator: %s\n' "${PAIRPILOT_PUBLIC_TAGGED_URL}"
printf 'Candidate peer service: %s\n' "${PAIRPILOT_PEER_TAGGED_URL}"
printf 'Production traffic was not changed. Tag: %s\n' "${PAIRPILOT_CANDIDATE_TAG}"
