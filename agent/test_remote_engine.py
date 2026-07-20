import vertexai
from vertexai import agent_engines
import os

PROJECT_ID = "acxiom-425322"
LOCATION = "us-central1"
REASONING_ENGINE_ID = "881159063860150272"

vertexai.init(project=PROJECT_ID, location=LOCATION)
remote_agent = agent_engines.get(f"projects/{PROJECT_ID}/locations/{LOCATION}/reasoningEngines/{REASONING_ENGINE_ID}")

print("Sending query...")
try:
    for event in remote_agent.stream_query(
        user_id="lKK7PPM62QYpdtCzrqrDcEm1aNs1",
        message="summarize acme service agreement"
    ):
        print("EVENT:", event)
except Exception as e:
    print("Error:", e)
