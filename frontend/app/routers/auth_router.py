"""
Routes for login, session creation, and logout.

Flow:
  1. GET /login          -> serves a page with the Firebase JS SDK sign-in widget
  2. (browser)           -> Firebase handles the Google OAuth popup, returns an ID token
  3. POST /session       -> browser sends the ID token here; we verify it and
                            set an httponly session cookie
  4. GET /logout         -> clears the cookie and revokes the Firebase session
"""

from fastapi import APIRouter, HTTPException, Request, Response, status
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from firebase_admin import auth as firebase_auth
from pydantic import BaseModel

from .. import config
from ..auth import create_session_cookie, get_current_user

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")


@router.get("/login")
async def login_page(request: Request):
    return templates.TemplateResponse(
        request,
        "login.html",
        {
            "firebase_api_key": config.FIREBASE_API_KEY,
            "firebase_auth_domain": config.FIREBASE_AUTH_DOMAIN,
            "firebase_project_id": config.FIREBASE_PROJECT_ID,
            "firebase_app_id": config.FIREBASE_APP_ID,
        },
    )


class SessionRequest(BaseModel):
    id_token: str


@router.post("/session")
async def create_session(body: SessionRequest, response: Response):
    session_cookie = create_session_cookie(body.id_token)
    response.set_cookie(
        key=config.SESSION_COOKIE_NAME,
        value=session_cookie,
        max_age=config.SESSION_COOKIE_MAX_AGE_SECONDS,
        httponly=True,
        secure=True,
        samesite="lax",
    )
    return {"status": "ok"}


@router.get("/logout")
async def logout(request: Request):
    cookie = request.cookies.get(config.SESSION_COOKIE_NAME)
    if cookie:
        try:
            decoded = firebase_auth.verify_session_cookie(cookie)
            firebase_auth.revoke_refresh_tokens(decoded["uid"])
        except Exception:  # noqa: BLE001 - logout should succeed even if verification fails


            pass

    redirect = RedirectResponse(url="/login", status_code=status.HTTP_303_SEE_OTHER)
    redirect.delete_cookie(config.SESSION_COOKIE_NAME)
    return redirect


@router.get("/")
async def root(request: Request):
    """Routes the logged-in user to the right home based on their role."""
    try:
        user = await get_current_user(request)
    except HTTPException:
        return RedirectResponse(url="/login")

    if user.is_operator:
        return RedirectResponse(url="/admin")
    return RedirectResponse(url="/chat")
