#!/usr/bin/env bash
set -euo pipefail

: "${GOOGLE_CLOUD_PROJECT:?Set GOOGLE_CLOUD_PROJECT}"
PAIRPILOT_REGION="${PAIRPILOT_REGION:-europe-west2}"
PAIRPILOT_MODEL_ID="${PAIRPILOT_MODEL_ID:-gemini-3.7-flash}"
GCLOUD="${GCLOUD:-gcloud}"
PAIRPILOT_RUNTIME_SA="pairpilot-runtime@${GOOGLE_CLOUD_PROJECT}.iam.gserviceaccount.com"
PAIRPILOT_TAG="${PAIRPILOT_TAG:-$(git rev-parse --short=12 HEAD)}"
PAIRPILOT_REPOSITORY="${PAIRPILOT_REGION}-docker.pkg.dev/${GOOGLE_CLOUD_PROJECT}/pairpilot"
PAIRPILOT_PEER_IMAGE="${PAIRPILOT_REPOSITORY}/peer-agents:${PAIRPILOT_TAG}"
PAIRPILOT_WEB_IMAGE="${PAIRPILOT_REPOSITORY}/orchestrator:${PAIRPILOT_TAG}"

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
  --min 0 --max 1 --concurrency 4 --cpu 1 --memory 512Mi --timeout 90 \
  --set-env-vars "GOOGLE_CLOUD_PROJECT=${GOOGLE_CLOUD_PROJECT},GOOGLE_CLOUD_LOCATION=global,PAIRPILOT_MODEL_ID=${PAIRPILOT_MODEL_ID},PAIRPILOT_PERSIST_PROVENANCE=true" \
  --quiet

PAIRPILOT_PEER_URL="$("${GCLOUD}" run services describe pairpilot-peer-agents \
  --project "${GOOGLE_CLOUD_PROJECT}" --region "${PAIRPILOT_REGION}" \
  --format 'value(status.url)')"

"${GCLOUD}" run services update pairpilot-peer-agents \
  --project "${GOOGLE_CLOUD_PROJECT}" \
  --region "${PAIRPILOT_REGION}" \
  --update-env-vars "PAIRPILOT_PUBLIC_BASE_URL=${PAIRPILOT_PEER_URL}" \
  --quiet >/dev/null

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
  --min 0 --max 1 --concurrency 4 --cpu 1 --memory 1Gi --timeout 120 \
  --startup-probe "httpGet.path=/api/health,httpGet.port=8080,timeoutSeconds=3,periodSeconds=5,failureThreshold=12" \
  --liveness-probe "httpGet.path=/api/health,httpGet.port=8080,initialDelaySeconds=5,timeoutSeconds=3,periodSeconds=30,failureThreshold=3" \
  --set-env-vars "GOOGLE_CLOUD_PROJECT=${GOOGLE_CLOUD_PROJECT},GOOGLE_CLOUD_LOCATION=global,PAIRPILOT_MODEL_ID=${PAIRPILOT_MODEL_ID},PAIRPILOT_PEER_BASE_URL=${PAIRPILOT_PEER_URL}" \
  --quiet

PAIRPILOT_PUBLIC_URL="$("${GCLOUD}" run services describe pairpilot-orchestrator \
  --project "${GOOGLE_CLOUD_PROJECT}" --region "${PAIRPILOT_REGION}" \
  --format 'value(status.url)')"

"${GCLOUD}" run services update pairpilot-orchestrator \
  --project "${GOOGLE_CLOUD_PROJECT}" \
  --region "${PAIRPILOT_REGION}" \
  --update-env-vars "PAIRPILOT_PUBLIC_BASE_URL=${PAIRPILOT_PUBLIC_URL}" \
  --quiet >/dev/null

echo "Public PairPilot URL: ${PAIRPILOT_PUBLIC_URL}"
