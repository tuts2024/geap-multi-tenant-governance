import os
from dotenv import load_dotenv
load_dotenv("frontend/.env")
os.chdir("agent")
import vertexai
from agent.agent import root_agent

PROJECT_ID = os.environ["GOOGLE_CLOUD_PROJECT"]
LOCATION = os.environ.get("GOOGLE_CLOUD_LOCATION", "us-central1")
STAGING_BUCKET = os.environ.get("STAGING_BUCKET", f"{PROJECT_ID}-agent-staging")

# Add gs:// prefix if missing
if not STAGING_BUCKET.startswith("gs://"):
    STAGING_BUCKET_URI = f"gs://{STAGING_BUCKET}"
else:
    STAGING_BUCKET_URI = STAGING_BUCKET

client = vertexai.Client(project=PROJECT_ID, location=LOCATION)

config = {
    "requirements": "requirements_simple.txt",
    "extra_packages": ["agent"],
    "env_vars": {
        "GCP_PROJECT_ID": PROJECT_ID,
        "GOOGLE_CLOUD_LOCATION": LOCATION,
        "OAUTH_CONTINUE_URI": os.environ.get(
            "OAUTH_CONTINUE_URI", "http://localhost:8080/oauth/validateUserId"
        ),
    },
    "display_name": "contract-analyst-gateway-demo",
    "identity_type": "AGENT_IDENTITY",
    # "agent_gateway_config": {
    #     "agent_to_anywhere_config": {
    #         "agent_gateway": "projects/learn-w-me/locations/us-central1/agentGateways/ag-egress-ge"
    #     }
    # },
    "staging_bucket": STAGING_BUCKET_URI
}

print(">> Deploying contract analyst agent with Agent Gateway (Client API)...")
try:
    remote_agent = client.agent_engines.create(
        agent=root_agent,
        config=config
    )
    print("")
    print("Deployed.")
    print(f"  Resource name:    {remote_agent.name}")
    print(f"  Reasoning engine: {remote_agent.name.split('/')[-1]}")
except Exception as e:
    print(f"Deployment failed: {e}")
    print("Trying with agent_engine argument...")
    try:
        from vertexai.agent_engines import AdkApp
        app = AdkApp(agent=root_agent, enable_tracing=True)
        remote_agent = client.agent_engines.create(
            agent_engine=app,
            config=config
        )
        print("")
        print("Deployed (via agent_engine).")
        print(f"  Resource name:    {remote_agent.name}")
        print(f"  Reasoning engine: {remote_agent.name.split('/')[-1]}")
    except Exception as e2:
        print(f"Redeployment failed again: {e2}")
