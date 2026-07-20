# Step 2: Register OAuth clients (manual console steps)

You need an OAuth 2.0 client registered in Google Cloud Console for Drive access.

| Provider | Auth server | Where you register |
|---|---|---|
| Google Drive | accounts.google.com | Google Cloud Console |

Each customer (Customer A, Customer B) will go through **3-legged OAuth (3LO)** against
this. The OAuth *client* (app registration) is shared — one client ID/secret for your
whole platform — but each **customer produces their own access/refresh token** when they
individually consent. That's the multi-tenant part: one client, many per-user grants.

---

## 2.1 Google Drive OAuth client

1. Go to **Google Cloud Console → APIs & Services → Credentials** (same project from step 1).
2. Click **Create Credentials → OAuth client ID**.
3. If prompted, configure the **OAuth consent screen** first:
   - User type: **External** (since Customer A / Customer B are outside your org), or
     **Internal** if everyone is in the same Google Workspace org.
   - App name: `Contract Analyst Agent`
   - Scopes: add `https://www.googleapis.com/auth/drive.readonly`
     (read-only is enough for an analysis agent — avoid requesting write/full Drive scope)
   - Add Customer A's and Customer B's test-user emails if the app is in "Testing" mode.
4. Application type: **Web application**.
5. Authorized redirect URI: this MUST be the `continue_uri` your frontend hosts —
   e.g. `https://YOUR_FRONTEND_DOMAIN/oauth/validateUserId`
6. Save the generated **Client ID** and **Client secret**. You'll enter these when creating
   the Agent Identity auth provider in step 3 — don't put them in agent code.

Scopes to request (keep minimal):
```
openid
email
https://www.googleapis.com/auth/drive.readonly
```

---

## 2.2 What goes where

| Value | Stored in |
|---|---|
| Google OAuth client ID/secret | Agent Identity auth provider config (step 3) — never in agent code |
| Per-customer access/refresh tokens | Managed entirely by Agent Identity at runtime — your code never touches raw tokens |

Next: `setup/03_create_auth_providers.sh` to register this client as an Agent Identity
auth provider and bind it to the agent's Drive tool.

---

Note: Confluence support has been removed from this demo for now. If you want it back,
the previous version of this doc registered a second OAuth client at
developer.atlassian.com/console/myapps with scopes `read:content:confluence`,
`read:space:confluence`, `read:page:confluence`, and `offline_access`. See git history.
