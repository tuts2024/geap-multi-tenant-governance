"""
Central configuration for the frontend app.

All values read from environment variables - nothing here is a secret.
Set these in a local .env (for `uvicorn` dev) or in your Cloud Run / App
Engine service config in production.
"""

import os
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

PROJECT_ID = os.environ.get("GOOGLE_CLOUD_PROJECT")
if not PROJECT_ID:
    PROJECT_ID = os.environ.get("PROJECT_ID")
    if not PROJECT_ID:
        raise KeyError("GOOGLE_CLOUD_PROJECT environment variable must be set (or defined in .env)")

LOCATION = os.environ.get("GOOGLE_CLOUD_LOCATION", "us-central1")

# Resource name of the deployed Agent Engine reasoning engine, e.g.
#   projects/123456789/locations/us-central1/reasoningEngines/987654321
AGENT_ENGINE_RESOURCE_NAME = os.environ["AGENT_ENGINE_RESOURCE_NAME"]

# Firebase project config - the web SDK config is NOT secret (it's sent to
# the browser), but keep it in env vars so it's easy to swap per environment.
FIREBASE_API_KEY = os.environ["FIREBASE_API_KEY"]
FIREBASE_AUTH_DOMAIN = os.environ["FIREBASE_AUTH_DOMAIN"]
FIREBASE_PROJECT_ID = os.environ.get("FIREBASE_PROJECT_ID", PROJECT_ID)
FIREBASE_APP_ID = os.environ["FIREBASE_APP_ID"]

# Cookie settings for the session cookie set after verifying the Firebase ID token.
SESSION_COOKIE_NAME = "session"
SESSION_COOKIE_MAX_AGE_SECONDS = 60 * 60 * 24 * 5  # 5 days, matches Firebase session default

# Custom claim key used to mark a user as the Operator/admin.
# Set via the Firebase Admin SDK (see setup/02_set_operator_claim.py) -
# never trust a client-supplied role value.
OPERATOR_CLAIM_KEY = "operator"

# This app's own base URL - used to build the OAuth continue_uri sent to
# Agent Identity. Must exactly match what's registered with the Google
# OAuth client (see agent repo's setup/02_create_oauth_clients.md).
APP_BASE_URL = os.environ.get("APP_BASE_URL", "http://localhost:8080")
OAUTH_CONTINUE_PATH = "/oauth/validateUserId"
