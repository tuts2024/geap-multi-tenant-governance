# Contract analyst agent - frontend

FastAPI app that handles login (Firebase Auth / Google), role-based routing
(Operator console vs customer chat), and hosts the OAuth `continue_uri` that
Agent Identity redirects to after a customer grants Drive access. Talks to
the agent from the companion `contract-analyst-agent` repo over
`vertexai.agent_engines`.

## Build order

| Step | File | What it does |
|---|---|---|
| 1 | `setup/01_enable_firebase.md` | **Manual.** Enable Firebase Auth (Google provider) on your GCP project |
| 2 | `setup/02_set_operator_claim.py` | Marks one Firebase user as the Operator via custom claim |
| - | `.env.example` | Copy to `.env`, fill in Firebase config + deployed agent's resource name |
| - | `pip install -r requirements.txt` | |
| - | `uvicorn app.main:app --reload --port 8080` | Run locally |

This assumes the agent from `contract-analyst-agent` is already deployed -
you need its `AGENT_ENGINE_RESOURCE_NAME` before this app can call it.

## Layout

```
app/
  main.py              FastAPI app, mounts all routers
  config.py            env-var based config
  auth.py              Firebase ID token verification, session cookie, role deps
  agent_client.py       wraps vertexai.agent_engines calls - the only chokepoint
                        for talking to the agent
  routers/
    auth_router.py      /login, /session, /logout, /
    chat_router.py      /chat, /api/chat  (customer-facing)
    admin_router.py      /admin and customer enable/disable (operator-only)
    oauth_router.py      /oauth/validateUserId  (Agent Identity continue_uri)
  templates/
    login.html, chat.html, admin.html
setup/
  01, 02...             see table above
docs/
  OPERATOR_NOTES.md     manual revocation steps, suggested customer data model
```

## Where the isolation guarantee lives, on THIS side

`app/agent_client.py`'s `ask_agent()` takes a `CurrentUser`, never a bare
string. `CurrentUser` is only ever constructed inside `app/auth.py`, from a
verified Firebase session cookie. There is no route, anywhere in this repo,
that reads a tenant/customer/user identifier out of a request body or query
param and uses it to call the agent. If you ever find yourself adding one,
that's the line not to cross - it's exactly the bypass that would defeat the
whole point of scoping by `user_id`.

## Known gaps / things to firm up before this is more than a demo

- The Drive "Connect" button in `chat.html` is stubbed - wiring the popup to
  the real `auth_request` event ADK emits when a tool needs a not-yet-granted
  credential needs to be confirmed against the live ADK client event schema
  before it'll actually work end to end.
- `oauth_router.py` assumes a `state` query param carries your session_id
  back from the OAuth redirect - verify the actual param Agent Identity
  appends before relying on this.
- The admin console's customer list reads directly from Firebase Auth -
  swap for a real Firestore-backed customer table per `docs/OPERATOR_NOTES.md`
  once you need real grant-status tracking.
