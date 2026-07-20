import os
import vertexai
from dotenv import load_dotenv

# Load configurations from the frontend env file
load_dotenv("frontend/.env")

# Change directory to agent/ to match other scripts
os.chdir("agent")

from vertexai.agent_engines import AdkApp
from agent.agent import root_agent

PROJECT_ID = os.environ.get("GOOGLE_CLOUD_PROJECT", "acxiom-425322")
LOCATION = os.environ.get("GOOGLE_CLOUD_LOCATION", "us-central1")
STAGING_BUCKET = os.environ.get("STAGING_BUCKET", "acxiom-425322-agent-staging")

if not STAGING_BUCKET.startswith("gs://"):
    STAGING_BUCKET_URI = f"gs://{STAGING_BUCKET}"
else:
    STAGING_BUCKET_URI = STAGING_BUCKET

# Using v1beta1 as seen in GitHub script
client = vertexai.Client(
    project=PROJECT_ID,
    location=LOCATION,
    http_options=dict(api_version="v1beta1"),
)

app = AdkApp(agent=root_agent, enable_tracing=True)

# Restoring full config pattern
config = {
    "requirements": "requirements_simple.txt",
    "extra_packages": ["agent"],
    "env_vars": {
        "GCP_PROJECT_ID": PROJECT_ID,
        "GOOGLE_CLOUD_LOCATION": LOCATION,
        "OAUTH_CONTINUE_URI": os.environ.get(
            "OAUTH_CONTINUE_URI", "http://localhost:8080/oauth/validateUserId"
        ),
        "GOOGLE_CLOUD_AGENT_ENGINE_ENABLE_TELEMETRY": "true",
        "OTEL_INSTRUMENTATION_GENAI_CAPTURE_MESSAGE_CONTENT": "true",
        "OTEL_TRACES_SAMPLER": "parentbased_traceidratio",
        "ADK_ENABLE_MCP_GRACEFUL_ERROR_HANDLING": "true",
    },
    "display_name": "contract-analyst-gateway-demo-linked",
    "identity_type": "AGENT_IDENTITY",
    "agent_gateway_config": {
        "agent_to_anywhere_config": {
            "agent_gateway": f"projects/{PROJECT_ID}/locations/{LOCATION}/agentGateways/agent-gateway"
        }
    },
    "staging_bucket": STAGING_BUCKET_URI
}

REASONING_ENGINE_NAME = f"projects/{PROJECT_ID}/locations/{LOCATION}/reasoningEngines/881159063860150272"

print(f">> Updating Reasoning Engine {REASONING_ENGINE_NAME} with Agent Gateway...")
try:
    # Use the app object as 'agent'
    engine = client.agent_engines.update(
        name=REASONING_ENGINE_NAME,
        agent=app,
        config=config
    )
    print("Updated successfully.")
    # Try accessing name via api_resource or directly
    engine_name = getattr(engine, "name", None)
    if not engine_name and hasattr(engine, "api_resource"):
        engine_name = getattr(engine.api_resource, "name", "Unknown")
    print(f"Resource name: {engine_name}")
except Exception as e:
    print(f"Update failed: {e}")
    print("Retrying with minimal config (Gateway only)...")
    try:
        minimal_config = {
            "agent_gateway_config": config["agent_gateway_config"]
        }
        engine = client.agent_engines.update(
            name=REASONING_ENGINE_NAME,
            config=minimal_config
        )
        print("Updated successfully (Minimal Config).")
        engine_name = getattr(engine, "name", None)
        if not engine_name and hasattr(engine, "api_resource"):
            engine_name = getattr(engine.api_resource, "name", "Unknown")
        print(f"Resource name: {engine_name}")
    except Exception as e2:
        print(f"Update failed again: {e2}")
