"""
Step 2 (frontend): mark one user as the Operator.

There is no UI for this on purpose - granting Operator/admin access should
be a deliberate, out-of-band action, not something reachable by any in-app
flow. Run this once per person who should have operator access.

Usage:
    python setup/02_set_operator_claim.py alice@yourcompany.com
"""

import sys

import firebase_admin
from firebase_admin import auth

firebase_admin.initialize_app()


def main(email: str):
    user = auth.get_user_by_email(email)
    auth.set_custom_user_claims(user.uid, {"operator": True})
    # Revoke existing tokens so the new claim takes effect on next sign-in
    # rather than waiting out the current token's expiry.
    auth.revoke_refresh_tokens(user.uid)
    print(f"Granted operator claim to {email} (uid={user.uid}).")
    print("They must sign out and back in for the claim to take effect.")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python setup/02_set_operator_claim.py <email>")
        sys.exit(1)
    main(sys.argv[1])
