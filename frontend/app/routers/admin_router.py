"""
Operator console.

Scope, deliberately kept honest for a demo: this shows which customers
exist and a placeholder grant status, and links to where an operator
actually revokes access today. As of this writing there's no confirmed
stable Agent Identity API for "revoke this one end-user's grant" distinct
from project-level IAM bindings or deleting the auth provider entirely -
see the comment in revoke_customer_grant() below before wiring a real
revoke button to anything.

Customer directory here is a placeholder in-memory list. Swap for a real
Firestore/Cloud SQL table keyed by uid in any real deployment - see
docs/OPERATOR_NOTES.md for the suggested schema.
"""

from fastapi import APIRouter, Depends, Request
from fastapi.templating import Jinja2Templates
from firebase_admin import auth as firebase_auth

from ..auth import CurrentUser, require_operator

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")


def _list_customers() -> list[dict]:
    """Lists non-operator Firebase users as 'customers' for the demo.

    Real deployments should back this with your own customer/tenant table
    (e.g. Firestore: customers/{uid} -> {tenant_name, drive_connected}),
    since Firebase alone doesn't track Drive grant status - Agent Identity
    does, and there's no documented per-uid status-read API yet (see module
    docstring).
    """
    customers = []
    for user in firebase_auth.list_users().iterate_all():
        is_operator = bool(user.custom_claims and user.custom_claims.get("operator"))
        if not is_operator:
            customers.append(
                {
                    "uid": user.uid,
                    "email": user.email,
                    "disabled": user.disabled,
                }
            )
    return customers


@router.get("/admin")
async def admin_console(request: Request, operator: CurrentUser = Depends(require_operator)):
    return templates.TemplateResponse(
        request,
        "index.html",
        {"operator_email": operator.email},
    )


@router.get("/admin/step1")
async def admin_step1(request: Request, operator: CurrentUser = Depends(require_operator)):
    return templates.TemplateResponse(request, "step1_setup.html", {})


@router.get("/admin/step2")
async def admin_step2(request: Request, operator: CurrentUser = Depends(require_operator)):
    return templates.TemplateResponse(request, "step2_shared_agent.html", {})


@router.get("/admin/catalog")
async def admin_catalog(request: Request, operator: CurrentUser = Depends(require_operator)):
    return templates.TemplateResponse(request, "client_catalog.html", {})


@router.get("/admin/creation")
async def admin_creation(request: Request, operator: CurrentUser = Depends(require_operator)):
    return templates.TemplateResponse(request, "agent_creation.html", {})


@router.get("/admin/model_isolation")
async def admin_model_isolation(request: Request, operator: CurrentUser = Depends(require_operator)):
    return templates.TemplateResponse(request, "model_isolation.html", {})


@router.post("/admin/customers/{uid}/disable")
async def disable_customer(uid: str, operator: CurrentUser = Depends(require_operator)):
    """Disables a customer's Firebase account - locks them out of login.

    This does NOT revoke their already-issued Drive tokens inside
    Agent Identity. For full offboarding you also need to revoke the
    relevant grant in Agent Identity / the underlying OAuth provider (see
    docs/OPERATOR_NOTES.md) - disabling login alone is necessary but not
    sufficient for a real production offboarding flow.
    """
    firebase_auth.update_user(uid, disabled=True)
    firebase_auth.revoke_refresh_tokens(uid)
    return {"status": "disabled", "uid": uid}


@router.post("/admin/customers/{uid}/enable")
async def enable_customer(uid: str, operator: CurrentUser = Depends(require_operator)):
    firebase_auth.update_user(uid, disabled=False)
    return {"status": "enabled", "uid": uid}
