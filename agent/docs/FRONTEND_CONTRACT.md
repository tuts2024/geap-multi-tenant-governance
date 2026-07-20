# Frontend integration contract

You said you're wiring up your own frontend/login. This is the exact contract
between your frontend and this agent - what your frontend must own, and what
the agent assumes is already true by the time it's called.

## What the agent assumes (do not skip these)

1. **The user is already authenticated** by the time you call the agent.
   Use Identity Platform / Google OIDC sign-in, or whatever IdP you choose -
   that's entirely your frontend's concern, not this agent's.

2. **You generate a stable `user_id`** per customer end-user (e.g. their
   Google `sub` claim, or your own internal user UUID). This is the value
   you pass as `user_id` to `async_stream_query`. Agent Engine Sessions and
   Agent Identity both key off this value - it IS the tenant/customer
   isolation boundary. Never let the user_id be client-suppliable in a way
   that lets one customer set it to another customer's value.

3. **You host the OAuth `continue_uri` / callback endpoint** for Google Drive
   (see setup/02_create_oauth_clients.md). When a tool call needs a
   credential that doesn't exist yet, ADK/Agent Identity triggers an
   interactive consent flow and redirects the user through your frontend
   back to this URI. Your handler there just needs to let the in-progress
   agent session resume - Agent Identity handles the token exchange and
   storage itself.

## Minimal call pattern

```python
from vertexai import agent_engines

remote_agent = agent_engines.get("projects/.../reasoningEngines/<id>")

async for event in remote_agent.async_stream_query(
    user_id=current_user.id,       # from YOUR auth session - never client input
    message=user_message,
    session_id=current_session_id,  # optional - lets you resume a conversation
):
    # stream event to your chat UI
    ...
```

## What NOT to build into your frontend

- Don't store Drive access or refresh tokens yourself - that's exactly the
  job Agent Identity now does. If your frontend is holding raw tokens,
  something's been wired wrong.
- Don't pass a "tenant_id" or "customer_id" as a chat message parameter or
  prompt content. The agent has no use for it and it shouldn't be a value
  the model could plausibly be talked into ignoring or overriding.
- Don't build separate agent deployments per customer. One agent, many
  user_ids - that's the whole point of this architecture.

## Operator console (separate small app, not covered by this repo)

You'll likely also want a small internal admin screen where the Operator can:
- See which customers have an active Drive grant
- Revoke a customer's auth provider grant (calls into Agent Identity's
  credential revocation - check current API for the exact method)
- View Agent Identity's audit log of tool-credential access per customer

This wasn't asked for in this build pass - flag if you want it scaffolded too.
