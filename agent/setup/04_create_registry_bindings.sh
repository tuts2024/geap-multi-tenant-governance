#!/usr/bin/env bash
# Step 4: Bind auth providers to this agent's tools via Agent Registry.
#
# A "binding" is what actually connects "this tool, on this agent" to
# "use this auth provider when it needs credentials." Without this, the
# auth provider exists but no tool knows to use it.

set -euo pipefail

PROJECT_ID="${PROJECT_ID:-your-gcp-project-id}"
LOCATION="${LOCATION:-us-central1}"

echo ">> Binding google_drive_search tool -> google-drive-3lo auth provider..."
gcloud alpha agent-registry bindings create contract-analyst-drive-binding \
  --project="${PROJECT_ID}" \
  --location="${LOCATION}" \
  --display-name="Contract Analyst - Google Drive" \
  --source-identifier="contract-analyst-agent/google_drive_tool" \
  --auth-provider="projects/${PROJECT_ID}/locations/${LOCATION}/connectors/google-drive-3lo" \
  || echo "   (already exists, skipping)"

echo ">> Binding the agent itself -> contract-analyst-self (2LO) for its own Vertex AI calls..."
gcloud alpha agent-registry bindings create contract-analyst-self-binding \
  --project="${PROJECT_ID}" \
  --location="${LOCATION}" \
  --display-name="Contract Analyst - self identity" \
  --source-identifier="contract-analyst-agent/self" \
  --auth-provider="projects/${PROJECT_ID}/locations/${LOCATION}/connectors/contract-analyst-self" \
  || echo "   (already exists, skipping)"

echo ""
echo "Done. Bindings created. The source-identifier strings above must match what the"
echo "agent code references - see agent/tools/*.py where GcpAuthProviderScheme(name=...)"
echo "points at these same connector resource paths."
echo ""
echo "Next: build and deploy the agent itself - see agent/ and setup/05_deploy_agent.sh"
