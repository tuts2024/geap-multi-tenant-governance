import os
import vertexai
from vertexai.agent_engines import AdkApp
from dotenv import load_dotenv

# Load configurations from the frontend env file
load_dotenv("frontend/.env")

# Change directory to agent/ to avoid packaging issues if needed
# os.chdir("agent") # Not needed if running from root and paths are absolute/correct

from agent.agent import root_agent

PROJECT_ID = "acxiom-425322"
LOCATION = "us-central1"
STAGING_BUCKET = "acxiom-425322-agent-staging"

if not STAGING_BUCKET.startswith("gs://"):
    STAGING_BUCKET_URI = f"gs://{STAGING_BUCKET}"
else:
    STAGING_BUCKET_URI = STAGING_BUCKET

# Using v1beta1 as seen in reference script
client = vertexai.Client(
    project=PROJECT_ID,
    location=LOCATION,
)

app = AdkApp(agent=root_agent, enable_tracing=True)

# Target the newly created agent
NEW_AGENT_ID = "881159063860150272"
REASONING_ENGINE_NAME = f"projects/{PROJECT_ID}/locations/{LOCATION}/reasoningEngines/{NEW_AGENT_ID}"

config = {
    "requirements": [
        "google-cloud-aiplatform[agent_engines,adk]>=1.112.0",
        "google-api-python-client",
        "google-auth",
        "httpx",
        "google-adk[agent-identity]",
        "google-cloud-bigquery",
        "mcp==1.28.1",
        "a2a-sdk==0.3.26",
        "pydantic",
        "cloudpickle",
        "google-cloud-datastore",
        "python-dotenv"
    ],
    "extra_packages": ["agent"],
    "env_vars": {
        "GOOGLE_CLOUD_LOCATION": LOCATION,
        "OAUTH_CONTINUE_URI": os.environ.get(
            "OAUTH_CONTINUE_URI", "http://localhost:8080/oauth/validateUserId"
        ),
    },
    "display_name": "contract-analyst-agent-linked-gateway",
    "identity_type": "AGENT_IDENTITY",
    "agent_gateway_config": {
        "agent_to_anywhere_config": {
            "agent_gateway": f"projects/{PROJECT_ID}/locations/{LOCATION}/agentGateways/agent-gateway"
        }
    },
    "staging_bucket": STAGING_BUCKET_URI
}

print(f">> Updating Reasoning Engine {REASONING_ENGINE_NAME} with Agent Gateway...")
try:
    engine = client.agent_engines.update(
        name=REASONING_ENGINE_NAME,
        agent=app,
        config=config
    )
    print("Updated successfully.")
    print(f"Resource name: {engine.name}")
except Exception as e:
    print(f"Update failed: {e}")
    print("Trying with agent_engine argument...")
    try:
        engine = client.agent_engines.update(
            name=REASONING_ENGINE_NAME,
            agent_engine=app,
            config=config
        )
        print("Updated successfully (via agent_engine).")
        print(f"Resource name: {engine.name}")
    except Exception as e2:
        print(f"Update failed again: {e2}")
