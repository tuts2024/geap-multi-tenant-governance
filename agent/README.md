# Contract analyst agent - multi-tenant GCP demo

ADK agent on Vertex AI Agent Engine. One Operator publishes it; Customer A and
Customer B each use it against their own Google Drive data only, isolated
via the Agent Identity auth manager (2LO for the agent's own identity, 3LO
per customer for Drive).

Note: Confluence support has been removed from this demo for now. See git
history if you want to bring it back - it followed the same 3LO pattern as
Drive, just against Atlassian's OAuth server instead of Google's.

## Build order

Run these in order. Steps 1, 3, 4 are scriptable; step 2 requires manual
console clicks (Google requires this - no API for it).

| Step | File | What it does |
|---|---|---|
| 1 | `setup/01_bootstrap_project.sh` | Enables APIs, creates staging bucket + agent service account |
| 2 | `setup/02_create_oauth_clients.md` | **Manual.** Register the Google Drive OAuth client |
| 3 | `setup/03_create_auth_providers.sh` | Creates the 2LO + 3LO Agent Identity auth providers |
| 4 | `setup/04_create_registry_bindings.sh` | Binds each auth provider to the agent's tools |
| 5 | `setup/05_deploy_agent.py` | Deploys the agent (`agent/`) to Vertex AI Agent Engine |
| 3 (again) | `setup/03_create_auth_providers.sh` | Re-run with `REASONING_ENGINE_ID` set, to grant the deployed agent IAM access to the providers |
| - | `setup/06_local_test.py` | Optional: simulate Customer A / Customer B sessions locally before/after deploy |

## Project layout

```
agent/
  __init__.py          exposes root_agent for adk CLI
  agent.py             the Agent definition - one agent, tenant-agnostic
  config.py            project/location/connector resource names
  requirements.txt
  tools/
    drive_tool.py       Drive search/fetch, 3LO-scoped per customer
setup/
  01-06...              build order, see table above
docs/
  FRONTEND_CONTRACT.md  exact contract for the frontend/login app you're building separately
```

## Where isolation actually lives

Not in the agent's prompt instructions (those are a backstop, not the
mechanism). It lives in:

1. `user_id` passed to `async_stream_query` - comes from your frontend's auth
   session, never from chat content.
2. Agent Identity's 3LO credential resolution - keyed off that `user_id`,
   resolved fresh per tool call, never cached in agent code or prompt context.
3. IAM bindings - the deployed agent (a specific reasoning engine) is the
   only principal granted `roles/iamconnectors.user` on these auth providers.

Same agent code path runs for both customers. Only the resolved credential
differs.

## Before you treat this as production

- `gcloud alpha agent-identity` / `gcloud alpha agent-registry` are preview
  surfaces - re-check flags against current docs before relying on them.
- Add real error handling / retry logic around the Drive API calls in
  `agent/tools/` - the version here is demo-minimal.
- Add token-revocation handling in your operator console (see
  `docs/FRONTEND_CONTRACT.md`, last section) so customers can be fully
  offboarded.
- Consider rate-limiting per `user_id` at your frontend, since nothing here
  stops a single customer from issuing a high volume of Drive calls through
  the agent.
