# Operator notes

## Revoking a customer's Drive grant

Disabling a customer in /admin (this app) revokes their *login* immediately
via `firebase_admin.auth.revoke_refresh_tokens`. It does NOT revoke any
Drive OAuth grant Agent Identity is holding for them.

As of this writing, the confirmed ways to fully revoke a specific
end-user's delegated grant are:

1. **Per-provider revocation at the source** - have the customer (or you,
   if you have admin rights on their Drive) revoke your app's access
   directly:
   - Google: https://myaccount.google.com/permissions
   This is the most reliable method today and works regardless of what
   Agent Identity exposes.

2. **Disable the auth provider entirely** (affects ALL customers, not just
   one) - only appropriate for an emergency/incident response, not routine
   offboarding:
   ```
   gcloud alpha agent-identity connectors update google-drive-3lo \
     --location=LOCATION --disable
   ```

There is no confirmed stable "revoke this one uid's token" API distinct
from the above as of mid-2026 - check current Agent Identity docs before
building an automated per-customer revoke button, since this is the kind
of preview-surface gap most likely to get filled in soon.

## Suggested customer/tenant data model (not yet wired up)

The admin console currently lists raw Firebase users. A real deployment
should back it with a proper table:

```
customers/{uid}
  email: string
  tenant_name: string           # "Customer A", "Customer B", etc.
  drive_connected: bool
  created_at: timestamp
```

Firestore is the natural fit given everything else here is already GCP.
Populate `drive_connected` by listening for the oauth-complete event from
`oauth_router.py` and writing a flag - Agent Identity itself doesn't
currently expose a documented per-user "is this provider connected" read
API, so track it yourself at that callback point.
