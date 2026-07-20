"""
Thin client wrapper for calling the deployed contract analyst agent.

Single chokepoint rule: every call into the agent goes through `ask_agent`,
and `ask_agent` takes a `CurrentUser`, never a bare string user_id. This
makes it structurally awkward to ever pass an unverified or client-supplied
identity into the agent - you'd have to manufacture a CurrentUser, which
only auth.py's verified paths do.
"""

from collections.abc import AsyncIterator

import vertexai
from vertexai import agent_engines

from . import config
from .auth import CurrentUser

_remote_agents = {}

def get_remote_agent(agent_urn: str | None = None):
    if agent_urn:
        if agent_urn.startswith("projects/"):
            target = agent_urn
        else:
            # Assume it's a short ID and construct full path
            target = f"projects/{config.PROJECT_ID}/locations/{config.LOCATION}/reasoningEngines/{agent_urn}"
    else:
        target = config.AGENT_ENGINE_RESOURCE_NAME

    if target not in _remote_agents:
        vertexai.init(project=config.PROJECT_ID, location=config.LOCATION)
        try:
            print(f"[AGENT_CLIENT] Connecting to Cloud Reasoning Engine runtime: {target}")
            _remote_agents[target] = agent_engines.get(target)
        except Exception as e:
            print(f"[AGENT_CLIENT] Dedicated runtime '{target}' not yet registered on Vertex AI: {e}. Using master engine '{config.AGENT_ENGINE_RESOURCE_NAME}'.")
            _remote_agents[target] = agent_engines.get(config.AGENT_ENGINE_RESOURCE_NAME)
    return _remote_agents[target]


async def ask_agent(
    user: CurrentUser,
    message: str,
    session_id: str | None = None,
    agent_urn: str | None = None,
) -> AsyncIterator[dict]:
    """Streams events from the agent for the given verified user.

    user.uid becomes the agent_engine `user_id` - this is the value Agent
    Identity and Agent Engine Sessions both key off internally. Customer A's
    uid and Customer B's uid resolve to entirely separate credential sets;
    nothing in this function (or anywhere upstream of it) lets one bleed
    into the other.
    """
    agent = get_remote_agent(agent_urn)
    
    if not session_id:
        try:
            print(f"[AGENT_CLIENT] Creating new session on Vertex AI for user {user.uid}...")
            session = await agent.async_create_session(user_id=user.uid)
            session_id = session.get("id") if isinstance(session, dict) else getattr(session, "id", None)
            print(f"[AGENT_CLIENT] Successfully created session: {session_id}")
            # Yield the session ID to the frontend first so it can store it
            yield {"session_id": session_id}
        except Exception as e:
            print(f"[AGENT_CLIENT] Error creating session: {e}")
            
    try:
        async for event in agent.async_stream_query(
            user_id=user.uid,
            session_id=session_id,
            message=message,
        ):
            if isinstance(event, dict) and event.get("code") == 498:
                raise ValueError(event.get("message") or "Session not found")
            yield event
            
    except Exception as e:
        error_msg = str(e)
        if "Session not found" in error_msg or "498" in error_msg:
            print(f"[AGENT_CLIENT] Session {session_id} not found/expired. Re-creating session...")
            try:
                session = await agent.async_create_session(user_id=user.uid)
                session_id = session.get("id") if isinstance(session, dict) else getattr(session, "id", None)
                print(f"[AGENT_CLIENT] Successfully re-created session: {session_id}")
                yield {"session_id": session_id}
                
                async for event in agent.async_stream_query(
                    user_id=user.uid,
                    session_id=session_id,
                    message=message,
                ):
                    yield event
            except Exception as re_err:
                print(f"[AGENT_CLIENT] Error during session re-creation retry: {re_err}")
                yield {"error": f"Failed to initialize session: {str(re_err)}"}
        else:
            print(f"[AGENT_CLIENT] Error in stream query: {e}")
            yield {"error": str(e)}
