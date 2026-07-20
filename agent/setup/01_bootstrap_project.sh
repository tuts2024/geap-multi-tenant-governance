#!/usr/bin/env bash
# Step 1: Bootstrap the existing GCP project for the contract analyst agent.
# Run from your local machine with gcloud authenticated:
#   gcloud auth login
#   gcloud config set project YOUR_PROJECT_ID
#
# This script is idempotent - safe to re-run.

set -euo pipefail

# ---- EDIT THESE ----
PROJECT_ID="${PROJECT_ID:-your-gcp-project-id}"
LOCATION="${LOCATION:-us-central1}"          # Vertex AI / Agent Engine region
STAGING_BUCKET="${STAGING_BUCKET:-${PROJECT_ID}-agent-staging}"
# ---------------------

echo ">> Using project: ${PROJECT_ID}"
gcloud config set project "${PROJECT_ID}"

echo ">> Enabling required APIs..."
gcloud services enable \
  aiplatform.googleapis.com \
  drive.googleapis.com \
  iam.googleapis.com \
  iamcredentials.googleapis.com \
  secretmanager.googleapis.com \
  cloudresourcemanager.googleapis.com \
  connectors.googleapis.com \
  --project="${PROJECT_ID}"

echo ">> Creating staging bucket for Agent Engine deployment (if missing)..."
if ! gsutil ls -b "gs://${STAGING_BUCKET}" >/dev/null 2>&1; then
  gsutil mb -l "${LOCATION}" "gs://${STAGING_BUCKET}"
else
  echo "   bucket gs://${STAGING_BUCKET} already exists, skipping"
fi

echo ">> Creating dedicated service account for the agent's own (2LO) identity..."
SA_NAME="contract-analyst-agent"
SA_EMAIL="${SA_NAME}@${PROJECT_ID}.iam.gserviceaccount.com"
if ! gcloud iam service-accounts describe "${SA_EMAIL}" >/dev/null 2>&1; then
  gcloud iam service-accounts create "${SA_NAME}" \
    --display-name="Contract Analyst Agent (2LO workload identity)"
else
  echo "   service account ${SA_EMAIL} already exists, skipping"
fi

echo ">> Granting minimal Vertex AI permissions to the agent service account..."
gcloud projects add-iam-policy-binding "${PROJECT_ID}" \
  --member="serviceAccount:${SA_EMAIL}" \
  --role="roles/aiplatform.user" \
  --condition=None

echo ">> Granting the Vertex AI Service Agent access to read secrets at deploy time..."
PROJECT_NUMBER=$(gcloud projects describe "${PROJECT_ID}" --format='value(projectNumber)')
VERTEX_SERVICE_AGENT="service-${PROJECT_NUMBER}@gcp-sa-aiplatform.iam.gserviceaccount.com"
gcloud projects add-iam-policy-binding "${PROJECT_ID}" \
  --member="serviceAccount:${VERTEX_SERVICE_AGENT}" \
  --role="roles/secretmanager.secretAccessor" \
  --condition=None

echo ""
echo "Done. Summary:"
echo "  Project:           ${PROJECT_ID}"
echo "  Location:          ${LOCATION}"
echo "  Staging bucket:    gs://${STAGING_BUCKET}"
echo "  Agent SA (2LO):    ${SA_EMAIL}"
echo "  Vertex Svc Agent:  ${VERTEX_SERVICE_AGENT}"
echo ""
echo "Next: setup/02_create_oauth_clients.md (manual console steps for Google OAuth)"
