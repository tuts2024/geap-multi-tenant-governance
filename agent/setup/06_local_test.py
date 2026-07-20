"""
Local smoke test - run the agent on your machine before deploying, simulating
Customer A and Customer B as two different ADK sessions/user_ids.

Note: this still requires real Agent Identity auth providers to exist (step 3),
since AuthenticatedFunctionTool resolves credentials through that service even
in local runs - there's no local-only stub for the 3LO flow.

Usage:
    python setup/06_local_test.py
"""

import asyncio

from vertexai import agent_engines

from agent.agent import root_agent


import agent
print("AGENT FILE:", agent.__file__)
import agent.agent
print("AGENT.AGENT FILE:", agent.agent.__file__)

async def run_as(user_id: str, message: str):
    app = agent_engines.AdkApp(agent=root_agent)
    print(f"\n--- session for user_id={user_id} ---")
    async for event in app.async_stream_query(user_id=user_id, message=message):
        print(event)


async def main():
    # Simulates Customer A's user logging in and asking about their contracts.
    await run_as(
        user_id="HfV08Bu3n4YPXgrPvAms1i9RzwK2", # Realistic User ID for Customer A
        message="Find any vendor agreements in my Drive and summarize the termination clause.",
    )

    # Test Spotify integration
    await run_as(
        user_id="HfV08Bu3n4YPXgrPvAms1i9RzwK2",
        message="What are my private Spotify playlists?",
    )

    # Test Confluence integration
    await run_as(
        user_id="loWmDyexCjMFhGkqV7MPZYwMnEf1", # Realistic User ID for Customer B
        message="Search Confluence for any documents related to contract onboarding.",
    )



if __name__ == "__main__":
    asyncio.run(main())
