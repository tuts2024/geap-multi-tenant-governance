#!/usr/bin/env bash
# Step 3: Create Agent Identity auth providers and grant the agent access to them.
#
# NOTE: `gcloud alpha agent-identity` and `gcloud alpha agent-registry` are PREVIEW
# surfaces as of mid-2026. Flag names may shift - run `gcloud alpha agent-identity
# connectors create --help` to confirm current flags before running this for real.
#
# Run AFTER setup/01_bootstrap_project.sh and AFTER you've registered the Drive
# OAuth client per setup/02_create_oauth_clients.md.

set -euo pipefail

# ---- EDIT THESE ----
PROJECT_ID="${PROJECT_ID:-your-gcp-project-id}"
LOCATION="${LOCATION:-us-central1}"
ORGANIZATION_ID="${ORGANIZATION_ID:-your-org-id}"   # gcloud organizations list

GOOGLE_DRIVE_CLIENT_ID="${GOOGLE_DRIVE_CLIENT_ID:-paste-from-step-2.1}"
GOOGLE_DRIVE_CLIENT_SECRET="${GOOGLE_DRIVE_CLIENT_SECRET:-paste-from-step-2.1}"

# This must match the redirect/callback URL your frontend hosts (step 2)
CONTINUE_URI="${CONTINUE_URI:-https://your-frontend-domain/oauth/validateUserId}"

# Set this AFTER you deploy the agent in step 5 (reasoning engine ID from output)
REASONING_ENGINE_ID="${REASONING_ENGINE_ID:-}"
# ---------------------

gcloud config set project "${PROJECT_ID}"
PROJECT_NUMBER=$(gcloud projects describe "${PROJECT_ID}" --format='value(projectNumber)')

echo ">> [2LO] Creating auth provider for the agent's OWN identity (calls to Vertex AI / Gemini)..."
echo "   This one does NOT need a client id/secret from a 3rd party - it represents the"
echo "   agent acting as itself, backed by the service account from step 1."
gcloud alpha agent-identity connectors create contract-analyst-self \
  --location="${LOCATION}" \
  --description="2LO identity for the contract analyst agent's own Vertex AI calls" \
  || echo "   (already exists, skipping)"

echo ""
echo ">> [3LO] Creating auth provider for Google Drive (per-customer delegated access)..."
gcloud alpha agent-identity connectors create google-drive-3lo \
  --location="${LOCATION}" \
  --description="Per-customer delegated Drive access for contract analysis" \
  --three-legged-oauth-client-id="${GOOGLE_DRIVE_CLIENT_ID}" \
  --three-legged-oauth-client-secret="${GOOGLE_DRIVE_CLIENT_SECRET}" \
  --three-legged-oauth-authorization-url="https://accounts.google.com/o/oauth2/v2/auth" \
  --three-legged-oauth-token-url="https://oauth2.googleapis.com/token" \
  || echo "   (already exists, skipping)"

echo ""
echo ">> Auth providers created. Retrieve the redirect URI Google generated -"
echo "   you must register THIS exact URI back in the Google OAuth client config"
echo "   from step 2 (the auth provider may generate its own proxy redirect URI - check"
echo "   the console output above or: gcloud alpha agent-identity connectors describe NAME)"
echo ""

if [[ -z "${REASONING_ENGINE_ID}" ]]; then
  echo ">> REASONING_ENGINE_ID not set yet - skipping IAM bindings."
  echo "   Deploy the agent first (step 5), then re-run this script with:"
  echo "   REASONING_ENGINE_ID=<id from deploy output> $0"
  exit 0
fi

AGENT_PRINCIPAL="principal://agents.global.org-${ORGANIZATION_ID}.system.id.goog/resources/aiplatform/projects/${PROJECT_NUMBER}/locations/${LOCATION}/reasoningEngines/${REASONING_ENGINE_ID}"

echo ">> Granting the deployed agent (${REASONING_ENGINE_ID}) access to both auth providers..."
for provider in contract-analyst-self google-drive-3lo; do
  echo "   binding roles/iamconnectors.user on ${provider} ..."
  gcloud projects add-iam-policy-binding "${PROJECT_ID}" \
    --role='roles/iamconnectors.user' \
    --member="${AGENT_PRINCIPAL}" \
    --condition=None
done

echo ""
echo "Done. Auth providers ready:"
echo "  contract-analyst-self  (2LO, agent's own identity)"
echo "  google-drive-3lo       (3LO, per-customer)"
echo ""
echo "Next: setup/04_create_registry_bindings.sh"
