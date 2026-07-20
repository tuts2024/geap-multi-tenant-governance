# Revised demo flow - scoped to this build

The original 9-step proposal (Section 7) describes a fuller agent platform
than what's built here: per-customer agent creation via API, per-agent
visibility/403 enforcement, multi-model config (Gemini vs Claude), and
natural-language agent configuration. Those are real, sizeable features -
not yet implemented in this repo (see "Not covered" below).

What IS built and demoable today is the core multi-tenant OAuth isolation
mechanism: one shared agent, two customers, each customer's tool calls
scoped strictly to their own Google Drive via per-user OAuth grants. This
revised flow walks through exactly that, honestly scoped to match the code.

## Step 1: Setup

Show the two Firebase Auth identities that stand in for Customer A and
Customer B (`setup/02_set_operator_claim.py` shows how the Operator is
distinguished from a customer via a custom claim - customers get no claim
at all). Note for the audience: this demo uses Firebase `uid` as the
tenant-scoping key rather than a separate IAM tenant construct - call this
out explicitly rather than implying a heavier-weight IAM tenancy setup
exists.

**Maps to:** original Step 1, narrowed - no IAM-console tenant view exists,
only the application-level identity boundary.

## Step 2: Deploy the shared agent

Run `agent/setup/05_deploy_agent.py`. Show the resulting `reasoningEngine`
resource. Make the point explicit: there is exactly one deployed agent.
Both Customer A and Customer B will call this same resource - the contract
analyst agent has no customer-specific code path.

**Maps to:** original Step 2, matches as proposed.

## Step 3: Connector auth - Customer A

Sign in to the frontend as Customer A. Click "Connect Google Drive,"
complete the OAuth consent screen, land back on `/oauth/validateUserId`.
Ask the agent something like "find vendor agreements in my Drive." Show
that results come only from Customer A's own Drive.

**Maps to:** original Step 3, matches - real Google OAuth, real Drive API
call, scoped via Agent Identity's 3LO resolution keyed on Customer A's
`user_id`.

## Step 4: Connector auth - Customer B

Sign out, sign in as Customer B. Repeat: connect Drive, ask the same kind
of question. Show that Customer B sees only Customer B's files - same
agent, same code path, different resolved credential. This is the
isolation guarantee made visible: nothing in the agent's prompt or code
branches on which customer is asking.

**Maps to:** original Step 4, matches as proposed.

## Step 5: Inline / delegated auth prompt

As a fresh customer (or after revoking a grant - see
`frontend/docs/OPERATOR_NOTES.md` for how), ask the agent a Drive-related
question with no prior Drive connection. Show the agent surfacing an
authorization request rather than failing silently or hallucinating an
answer, and the user completing consent mid-conversation.

**Maps to:** original Step 9. Note: the actual button-click-to-popup wiring
in `chat.html` is still a stub as of this build (flagged in
`frontend/README.md` "known gaps") - confirm the live ADK `auth_request`
event shape before relying on this working end-to-end in a live demo. If
it's not ready, narrate this step instead of running it live.

---

## Not covered in this build (original Steps 5-8)

Flag these to the audience as roadmap, not "coming in this demo":

- **Per-customer agent creation via API** (original Step 5) - this build
  has one Operator-deployed agent shared by all customers, not a
  platform API customers call to provision their own agent instances.
- **Cross-customer visibility / 403 enforcement on agent access** (original
  Step 6) - doesn't apply yet since there's only one shared agent; there's
  no per-agent ACL to test a 403 against.
- **Multi-model / per-agent model config, including non-Google models**
  (original Step 7) - the agent has one hardcoded Gemini model
  (`agent/agent/config.py: GEMINI_MODEL`). No per-customer or per-agent
  override exists.
- **Natural-language agent configuration** (original Step 8) - no such
  feature exists in this repo.

If the validation specifically requires these, they're a separate, larger
build - effectively a slice of an agent-platform control plane (agent
provisioning, ACLs, model registry, NL-driven config) layered on top of
what exists today, rather than an extension of the contract analyst agent
itself.
