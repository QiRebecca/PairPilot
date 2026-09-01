#!/usr/bin/env bash
set -euo pipefail

: "${GOOGLE_CLOUD_PROJECT:?Set GOOGLE_CLOUD_PROJECT}"
: "${PAIRPILOT_DEPLOY_CANDIDATE:?Set PAIRPILOT_DEPLOY_CANDIDATE}"
if [[ "${PAIRPILOT_DEPLOY_CANDIDATE}" != "DEPLOY_ISOLATED_V2_CANDIDATE" ]]; then
  echo "Refusing candidate deployment without the exact confirmation phrase." >&2
  exit 2
fi

PAIRPILOT_REGION="${PAIRPILOT_REGION:-europe-west2}"
PAIRPILOT_MODEL_ID="${PAIRPILOT_MODEL_ID:-gemini-3.7-flash}"
PAIRPILOT_CANDIDATE_TAG="${PAIRPILOT_CANDIDATE_TAG:-startup-v2-candidate}"
PAIRPILOT_RUNTIME_SA="pairpilot-runtime@${GOOGLE_CLOUD_PROJECT}.iam.gserviceaccount.com"
PAIRPILOT_IMAGE_TAG="${PAIRPILOT_IMAGE_TAG:-startup-v2-$(git rev-parse --short=12 HEAD)}"
PAIRPILOT_REPOSITORY="${PAIRPILOT_REGION}-docker.pkg.dev/${GOOGLE_CLOUD_PROJECT}/pairpilot"
PAIRPILOT_IMAGE="${PAIRPILOT_REPOSITORY}/orchestrator:${PAIRPILOT_IMAGE_TAG}"
PAIRPILOT_SERVICE="pairpilot-orchestrator"
PAIRPILOT_TOPIC="pairpilot-v2-candidate-events"
PAIRPILOT_DLQ_TOPIC="pairpilot-v2-candidate-dlq"
PAIRPILOT_SUBSCRIPTION="pairpilot-v2-candidate-worker"

BASE_URL="$(gcloud run services describe "${PAIRPILOT_SERVICE}" \
  --project "${GOOGLE_CLOUD_PROJECT}" --region "${PAIRPILOT_REGION}" \
  --format 'value(status.url)')"
CANDIDATE_URL="https://${PAIRPILOT_CANDIDATE_TAG}---${BASE_URL#https://}"

ACCESS_TOKEN="$(gcloud auth print-access-token)"
WEB_APP_ID="$(curl -fsS \
  -H "Authorization: Bearer ${ACCESS_TOKEN}" \
  -H "X-Goog-User-Project: ${GOOGLE_CLOUD_PROJECT}" \
  "https://firebase.googleapis.com/v1beta1/projects/${GOOGLE_CLOUD_PROJECT}/webApps?pageSize=100" \
  | jq -r '.apps[] | select(.displayName == "PairPilot Public Beta Web") | .appId')"
WEB_CONFIG="$(curl -fsS \
  -H "Authorization: Bearer ${ACCESS_TOKEN}" \
  -H "X-Goog-User-Project: ${GOOGLE_CLOUD_PROJECT}" \
  "https://firebase.googleapis.com/v1beta1/projects/${GOOGLE_CLOUD_PROJECT}/webApps/${WEB_APP_ID}/config")"

gcloud pubsub topics describe "${PAIRPILOT_TOPIC}" \
  --project "${GOOGLE_CLOUD_PROJECT}" >/dev/null 2>&1 || \
  gcloud pubsub topics create "${PAIRPILOT_TOPIC}" \
    --project "${GOOGLE_CLOUD_PROJECT}"
gcloud pubsub topics describe "${PAIRPILOT_DLQ_TOPIC}" \
  --project "${GOOGLE_CLOUD_PROJECT}" >/dev/null 2>&1 || \
  gcloud pubsub topics create "${PAIRPILOT_DLQ_TOPIC}" \
    --project "${GOOGLE_CLOUD_PROJECT}"

gcloud builds submit \
  --project "${GOOGLE_CLOUD_PROJECT}" \
  --region "${PAIRPILOT_REGION}" \
  --config infra/cloudbuild-orchestrator.yaml \
  --substitutions "_IMAGE=${PAIRPILOT_IMAGE}" .

gcloud run deploy "${PAIRPILOT_SERVICE}" \
  --project "${GOOGLE_CLOUD_PROJECT}" \
  --region "${PAIRPILOT_REGION}" \
  --image "${PAIRPILOT_IMAGE}" \
  --service-account "${PAIRPILOT_RUNTIME_SA}" \
  --allow-unauthenticated \
  --no-traffic \
  --tag "${PAIRPILOT_CANDIDATE_TAG}" \
  --min 0 --max 3 --concurrency 16 --cpu 1 --memory 1Gi --timeout 120 \
  --startup-probe "httpGet.path=/api/health,httpGet.port=8080,timeoutSeconds=3,periodSeconds=5,failureThreshold=12" \
  --liveness-probe "httpGet.path=/api/health,httpGet.port=8080,initialDelaySeconds=5,timeoutSeconds=3,periodSeconds=30,failureThreshold=3" \
  --set-env-vars "GOOGLE_CLOUD_PROJECT=${GOOGLE_CLOUD_PROJECT},GOOGLE_CLOUD_LOCATION=global,PAIRPILOT_MODEL_ID=${PAIRPILOT_MODEL_ID},PAIRPILOT_PUBLIC_BASE_URL=${CANDIDATE_URL},PAIRPILOT_INTERNAL_AUDIENCE=${CANDIDATE_URL},PAIRPILOT_ENVIRONMENT=candidate,PAIRPILOT_COLLECTION_PREFIX=candidate_v2_,PAIRPILOT_EVENT_TOPIC_ID=${PAIRPILOT_TOPIC},PAIRPILOT_FIREBASE_API_KEY=$(printf '%s' "${WEB_CONFIG}" | jq -r .apiKey),PAIRPILOT_FIREBASE_AUTH_DOMAIN=$(printf '%s' "${WEB_CONFIG}" | jq -r .authDomain),PAIRPILOT_FIREBASE_APP_ID=$(printf '%s' "${WEB_CONFIG}" | jq -r .appId),PAIRPILOT_FIREBASE_MESSAGING_SENDER_ID=$(printf '%s' "${WEB_CONFIG}" | jq -r .messagingSenderId),PAIRPILOT_FIREBASE_STORAGE_BUCKET=$(printf '%s' "${WEB_CONFIG}" | jq -r .storageBucket)" \
  --quiet

if gcloud pubsub subscriptions describe "${PAIRPILOT_SUBSCRIPTION}" \
  --project "${GOOGLE_CLOUD_PROJECT}" >/dev/null 2>&1; then
  gcloud pubsub subscriptions update "${PAIRPILOT_SUBSCRIPTION}" \
    --project "${GOOGLE_CLOUD_PROJECT}" \
    --push-endpoint "${CANDIDATE_URL}/api/internal/events" \
    --push-auth-service-account "${PAIRPILOT_RUNTIME_SA}" \
    --push-auth-token-audience "${CANDIDATE_URL}" \
    --dead-letter-topic "${PAIRPILOT_DLQ_TOPIC}" \
    --max-delivery-attempts 5
else
  gcloud pubsub subscriptions create "${PAIRPILOT_SUBSCRIPTION}" \
    --project "${GOOGLE_CLOUD_PROJECT}" \
    --topic "${PAIRPILOT_TOPIC}" \
    --push-endpoint "${CANDIDATE_URL}/api/internal/events" \
    --push-auth-service-account "${PAIRPILOT_RUNTIME_SA}" \
    --push-auth-token-audience "${CANDIDATE_URL}" \
    --dead-letter-topic "${PAIRPILOT_DLQ_TOPIC}" \
    --max-delivery-attempts 5 \
    --min-retry-delay 10s \
    --max-retry-delay 120s
fi

REVISION="$(gcloud run revisions list \
  --project "${GOOGLE_CLOUD_PROJECT}" --region "${PAIRPILOT_REGION}" \
  --service "${PAIRPILOT_SERVICE}" --sort-by='~metadata.creationTimestamp' \
  --limit 1 --format='value(metadata.name)')"
DIGEST="$(gcloud artifacts docker images describe "${PAIRPILOT_IMAGE}" \
  --project "${GOOGLE_CLOUD_PROJECT}" --format='value(image_summary.digest)')"

echo "Candidate URL: ${CANDIDATE_URL}"
echo "Candidate revision: ${REVISION}"
echo "Image digest: ${DIGEST}"
echo "Collections: candidate_v2_*"
echo "Pub/Sub: ${PAIRPILOT_TOPIC} -> ${PAIRPILOT_SUBSCRIPTION} -> candidate tag"
echo "Production traffic was not changed."
