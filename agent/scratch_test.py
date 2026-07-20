import vertexai
from vertexai import agent_engines
import json

vertexai.init(project="learn-w-me", location="us-central1")
remote_agent = agent_engines.get("projects/404109417257/locations/us-central1/reasoningEngines/7838750996682506240")

print("Sending query...")
try:
    for event in remote_agent.stream_query(
        user_id="8AuDYoB31DMMSLcAn3FYG3BoK1v2",
        message="I am looking for sow"
    ):
        print("EVENT:", type(event), event)
except Exception as e:
    print("Error:", e)
