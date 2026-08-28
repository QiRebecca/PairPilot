#!/usr/bin/env bash
set -euo pipefail

: "${GOOGLE_CLOUD_PROJECT:?Set GOOGLE_CLOUD_PROJECT to the dedicated project ID}"
PAIRPILOT_REGION="${PAIRPILOT_REGION:-europe-west2}"
PAIRPILOT_RUNTIME_SA="pairpilot-runtime@${GOOGLE_CLOUD_PROJECT}.iam.gserviceaccount.com"
GCLOUD="${GCLOUD:-gcloud}"

required_services=(
  aiplatform.googleapis.com
  artifactregistry.googleapis.com
  billingbudgets.googleapis.com
  cloudbuild.googleapis.com
  firestore.googleapis.com
  iam.googleapis.com
  logging.googleapis.com
  pubsub.googleapis.com
  run.googleapis.com
  serviceusage.googleapis.com
)

"${GCLOUD}" services enable "${required_services[@]}" \
  --project "${GOOGLE_CLOUD_PROJECT}"

if ! "${GCLOUD}" artifacts repositories describe pairpilot \
  --project "${GOOGLE_CLOUD_PROJECT}" \
  --location "${PAIRPILOT_REGION}" >/dev/null 2>&1; then
  "${GCLOUD}" artifacts repositories create pairpilot \
    --project "${GOOGLE_CLOUD_PROJECT}" \
    --location "${PAIRPILOT_REGION}" \
    --repository-format docker \
    --description "PairPilot hackathon containers"
fi

if ! "${GCLOUD}" iam service-accounts describe "${PAIRPILOT_RUNTIME_SA}" \
  --project "${GOOGLE_CLOUD_PROJECT}" >/dev/null 2>&1; then
  "${GCLOUD}" iam service-accounts create pairpilot-runtime \
    --project "${GOOGLE_CLOUD_PROJECT}" \
    --display-name "PairPilot runtime"
fi

for role in roles/aiplatform.user roles/datastore.user roles/pubsub.publisher; do
  "${GCLOUD}" projects add-iam-policy-binding "${GOOGLE_CLOUD_PROJECT}" \
    --member "serviceAccount:${PAIRPILOT_RUNTIME_SA}" \
    --role "${role}" \
    --condition None >/dev/null
done

if ! "${GCLOUD}" pubsub topics describe pairpilot-events \
  --project "${GOOGLE_CLOUD_PROJECT}" >/dev/null 2>&1; then
  "${GCLOUD}" pubsub topics create pairpilot-events \
    --project "${GOOGLE_CLOUD_PROJECT}"
fi

echo "Bootstrap complete for ${GOOGLE_CLOUD_PROJECT} in ${PAIRPILOT_REGION}."
echo "Billing linkage, Firestore location, and budget alerts require explicit owner review."
