"""
Central configuration for the contract analyst agent.

Keep all GCP resource identifiers here so tools and the agent definition
don't hardcode strings in multiple places. Values are read from environment
variables at runtime (set these in your Agent Engine deployment config or
local .env for testing) - nothing here is a secret.
"""

import os
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

PROJECT_ID = os.environ.get("GOOGLE_CLOUD_PROJECT")
if not PROJECT_ID or PROJECT_ID.isdigit():
    PROJECT_ID = os.environ.get("GCP_PROJECT_ID")
    if not PROJECT_ID:
        raise KeyError("GOOGLE_CLOUD_PROJECT (or GCP_PROJECT_ID) environment variable must be set (or defined in .env)")

LOCATION = os.environ.get("GOOGLE_CLOUD_LOCATION", "us-central1")

# Agent Identity connector resource names (created in setup/03_create_auth_providers.sh)
AGENT_SELF_AUTH_PROVIDER = os.environ.get(
    "AGENT_SELF_AUTH_PROVIDER",
    f"projects/{PROJECT_ID}/locations/{LOCATION}/connectors/contract-analyst-self"
)
GOOGLE_DRIVE_AUTH_PROVIDER = os.environ.get(
    "GOOGLE_DRIVE_AUTH_PROVIDER",
    f"projects/{PROJECT_ID}/locations/{LOCATION}/connectors/google-drive-3lo"
)
SPOTIFY_3LO_AUTH_PROVIDER = os.environ.get(
    "SPOTIFY_3LO_AUTH_PROVIDER",
    f"projects/{PROJECT_ID}/locations/{LOCATION}/connectors/spotify-3lo-connector"
)
CONFLUENCE_AUTH_PROVIDER = os.environ.get(
    "CONFLUENCE_AUTH_PROVIDER",
    f"projects/{PROJECT_ID}/locations/{LOCATION}/connectors/confluence-3lo"
)

# This URI must be hosted by YOUR frontend (not this agent) and must match
# the redirect URI registered with both Google and Atlassian OAuth clients.
# It's where the user lands after granting consent; your frontend's handler
# there is responsible for resuming the ADK session.
OAUTH_CONTINUE_URI = os.environ.get(
    "OAUTH_CONTINUE_URI", "http://localhost:8080/oauth/validateUserId"
)

GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash")

# Agent Registry Endpoint IDs
CONFLUENCE_ENDPOINT_ID = os.environ.get(
    "CONFLUENCE_ENDPOINT_ID",
    "agentregistry-00000000-0000-0000-9073-e705dfc46425"
)
SPOTIFY_ENDPOINT_ID = os.environ.get(
    "SPOTIFY_ENDPOINT_ID",
    "agentregistry-00000000-0000-0000-4e1c-3189bee34dd6"
)

