#!/usr/bin/env bash
set -euo pipefail

: "${GOOGLE_CLOUD_PROJECT:?Set GOOGLE_CLOUD_PROJECT}"
PAIRPILOT_REGION="${PAIRPILOT_REGION:-europe-west2}"
PAIRPILOT_MODEL_ID="${PAIRPILOT_MODEL_ID:-gemini-3.7-flash}"
PAIRPILOT_CANDIDATE_TAG="${PAIRPILOT_CANDIDATE_TAG:-multi-user-beta}"
PAIRPILOT_RUNTIME_SA="pairpilot-runtime@${GOOGLE_CLOUD_PROJECT}.iam.gserviceaccount.com"
PAIRPILOT_IMAGE_TAG="${PAIRPILOT_IMAGE_TAG:-multi-user-beta-$(git rev-parse --short=12 HEAD)}"
PAIRPILOT_REPOSITORY="${PAIRPILOT_REGION}-docker.pkg.dev/${GOOGLE_CLOUD_PROJECT}/pairpilot"
PAIRPILOT_IMAGE="${PAIRPILOT_REPOSITORY}/orchestrator:${PAIRPILOT_IMAGE_TAG}"
PAIRPILOT_SERVICE="pairpilot-orchestrator"

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
  --set-env-vars "GOOGLE_CLOUD_PROJECT=${GOOGLE_CLOUD_PROJECT},GOOGLE_CLOUD_LOCATION=global,PAIRPILOT_MODEL_ID=${PAIRPILOT_MODEL_ID},PAIRPILOT_PUBLIC_BASE_URL=${CANDIDATE_URL},PAIRPILOT_INTERNAL_AUDIENCE=${CANDIDATE_URL},PAIRPILOT_FIREBASE_API_KEY=$(printf '%s' "${WEB_CONFIG}" | jq -r .apiKey),PAIRPILOT_FIREBASE_AUTH_DOMAIN=$(printf '%s' "${WEB_CONFIG}" | jq -r .authDomain),PAIRPILOT_FIREBASE_APP_ID=$(printf '%s' "${WEB_CONFIG}" | jq -r .appId),PAIRPILOT_FIREBASE_MESSAGING_SENDER_ID=$(printf '%s' "${WEB_CONFIG}" | jq -r .messagingSenderId),PAIRPILOT_FIREBASE_STORAGE_BUCKET=$(printf '%s' "${WEB_CONFIG}" | jq -r .storageBucket)" \
  --quiet

printf 'Candidate orchestrator: %s\n' "${CANDIDATE_URL}"
printf 'Production traffic was not changed. Tag: %s\n' "${PAIRPILOT_CANDIDATE_TAG}"
