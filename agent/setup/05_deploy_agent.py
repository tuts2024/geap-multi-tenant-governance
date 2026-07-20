"""
Step 5: Deploy the contract analyst agent to Vertex AI Agent Engine.

Run from the project root with the venv active:
    python setup/05_deploy_agent.py

This is a one-time (or per-update) operator action - customers never run this.
"""

import os
from dotenv import load_dotenv

# Load configurations from the frontend env file
load_dotenv("frontend/.env")

# Change directory to agent/ to avoid packaging the virtual environment (.venv)
os.chdir("agent")

import vertexai
from vertexai import agent_engines

from agent.agent import root_agent

PROJECT_ID = os.environ["GOOGLE_CLOUD_PROJECT"]
LOCATION = os.environ.get("GOOGLE_CLOUD_LOCATION", "us-central1")
STAGING_BUCKET = os.environ.get("STAGING_BUCKET", f"{PROJECT_ID}-agent-staging")
if not STAGING_BUCKET.startswith("gs://"):
    STAGING_BUCKET = f"gs://{STAGING_BUCKET}"

vertexai.init(project=PROJECT_ID, location=LOCATION, staging_bucket=STAGING_BUCKET)

app = agent_engines.AdkApp(agent=root_agent, enable_tracing=True)

resource_name = os.environ.get("AGENT_ENGINE_RESOURCE_NAME")

if resource_name:
    print(f">> Updating existing contract analyst agent in Vertex AI Agent Engine: {resource_name}")
    remote_agent = agent_engines.update(
        resource_name=resource_name,
        agent_engine=app,
        requirements="requirements_simple.txt",
        extra_packages=["agent"],
        env_vars={
            "GCP_PROJECT_ID": PROJECT_ID,
            "GOOGLE_CLOUD_LOCATION": LOCATION,
            "OAUTH_CONTINUE_URI": os.environ.get(
                "OAUTH_CONTINUE_URI", "http://localhost:8080/oauth/validateUserId"
            ),
            "WORKSPACE_DWD_SA_EMAIL": os.environ.get("WORKSPACE_DWD_SA_EMAIL", ""),
        },
    )
else:
    print(">> Deploying new contract analyst agent to Vertex AI Agent Engine...")
    remote_agent = agent_engines.create(
        agent_engine=app,
        requirements="requirements_simple.txt",
        extra_packages=["agent"],
        env_vars={
            "GCP_PROJECT_ID": PROJECT_ID,
            "GOOGLE_CLOUD_LOCATION": LOCATION,
            "OAUTH_CONTINUE_URI": os.environ.get(
                "OAUTH_CONTINUE_URI", "http://localhost:8080/oauth/validateUserId"
            ),
            "WORKSPACE_DWD_SA_EMAIL": os.environ.get("WORKSPACE_DWD_SA_EMAIL", ""),
        },
        display_name="contract-analyst-agent",
    )

print("")
print("Deployed.")
print(f"  Resource name:    {remote_agent.resource_name}")
print(f"  Reasoning engine: {remote_agent.resource_name.split('/')[-1]}")
print("")
print("Next:")
print("  1. Copy the reasoning engine ID above.")
print("  2. Re-run setup/03_create_auth_providers.sh with REASONING_ENGINE_ID=<id>")
print("     to grant this deployed agent access to the auth providers.")
print("  3. Your frontend calls this agent via remote_agent.async_stream_query(")
print("     user_id=<customer's authenticated user id>, message=...)")
