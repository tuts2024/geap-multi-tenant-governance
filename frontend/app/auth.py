"""
Auth core: Firebase ID token verification, session cookie issuance, and
FastAPI dependencies for "current user" and "current user must be operator".

Design point worth keeping in mind while reading this file: the `user_id`
this module produces (the Firebase `uid`) is the SAME value passed to the
agent as `user_id` in `agent_client.py`. That's deliberate - it's the one
identity value that threads all the way from "who logged in" to "whose
Drive token Agent Identity resolves." Nothing here lets a client
override it; it always comes from a verified token or a verified session
cookie, never from request body/query params.
"""

from dataclasses import dataclass

import firebase_admin
from fastapi import Depends, HTTPException, Request, status
from firebase_admin import auth as firebase_auth

from . import config

if not firebase_admin._apps:
    # Uses Application Default Credentials - no key file needed when running
    # on Cloud Run / GCE / Agent Engine with the right service account attached.
    firebase_admin.initialize_app(options={'projectId': config.FIREBASE_PROJECT_ID})


@dataclass
class CurrentUser:
    uid: str
    email: str | None
    is_operator: bool


def _decode_session_cookie(session_cookie: str) -> CurrentUser:
    try:
        decoded = firebase_auth.verify_session_cookie(session_cookie, check_revoked=True)
    except firebase_auth.InvalidSessionCookieError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Session expired or invalid."
        ) from exc



    return CurrentUser(
        uid=decoded["uid"],
        email=decoded.get("email"),
        is_operator=bool(decoded.get(config.OPERATOR_CLAIM_KEY, False)),
    )


async def get_current_user(request: Request) -> CurrentUser:
    """FastAPI dependency: resolves the logged-in user from the session cookie.

    Raises 401 if there's no valid session - routes that need a logged-in
    user should depend on this directly; routes that should redirect to
    /login instead can catch the HTTPException in their own handler.
    """
    cookie = request.cookies.get(config.SESSION_COOKIE_NAME)
    if not cookie:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not signed in.")
    return _decode_session_cookie(cookie)


async def require_operator(user: CurrentUser = Depends(get_current_user)) -> CurrentUser:
    """FastAPI dependency: like get_current_user, but also requires the
    operator custom claim. Use this on every /admin route.
    """
    if not user.is_operator:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This area is restricted to the Operator.",
        )
    return user


def create_session_cookie(id_token: str) -> str:
    """Exchanges a verified Firebase ID token (from the client SDK) for a
    longer-lived session cookie value, stored as an httponly cookie.

    This also re-verifies the ID token itself before minting the cookie -
    never trust the client's claim that it's already valid.
    """
    try:
        firebase_auth.verify_id_token(id_token, check_revoked=True)
    except Exception as exc:  # noqa: BLE001 - surfacing as a clean 401 below
        import traceback
        print(f"[AUTH_ERROR] verify_id_token failed: {exc}", flush=True)
        traceback.print_exc()
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid ID token."
        ) from exc

    return firebase_auth.create_session_cookie(
        id_token, expires_in=config.SESSION_COOKIE_MAX_AGE_SECONDS
    )


