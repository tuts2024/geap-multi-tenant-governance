"""
Hosts the `continue_uri` registered with Agent Identity's 3LO auth provider
(see agent repo's agent/config.py: OAUTH_CONTINUE_URI, and
setup/02_create_oauth_clients.md for where this exact path must also be
registered with Google's OAuth client config).

IMPORTANT - what this endpoint does NOT do: it does not see, store, or
exchange any access/refresh token. By the time the browser lands here,
Agent Identity has already completed the token exchange server-side. This
endpoint's only job is to let the in-flight agent session resume.

Confirm the exact query params Agent Identity appends to this redirect
against current docs before wiring this for real - the example below
assumes a `state` param that round-trips your session_id, which is the
standard OAuth pattern but the precise param names here may differ.
"""

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
import httpx
import google.auth
import google.auth.transport.requests

from ..auth import CurrentUser, get_current_user

router = APIRouter()


@router.get("/oauth/validateUserId")
async def oauth_continue(
    request: Request,
    user: CurrentUser = Depends(get_current_user),
):
    user_id_validation_state = request.query_params.get("user_id_validation_state")
    connector_name = request.query_params.get("connector_name")
    consent_nonce = request.cookies.get("consent_nonce", "")

    print(f"[OAUTH] Completed OAuth redirect. state={user_id_validation_state}, connector={connector_name}, user_id={user.uid}, consent_nonce='{consent_nonce}'")

    if not user_id_validation_state or not connector_name:
        print("[OAUTH] Missing required validation state or connector name!")
        return HTMLResponse("Missing required validation state or connector name", status_code=400)

    try:
        # Call the Google Cloud IAM Connector Credentials credentials:finalize endpoint
        url = f"https://iamconnectorcredentials.googleapis.com/v1alpha/{connector_name}/credentials:finalize"
        
        creds, _ = google.auth.default()
        creds.refresh(google.auth.transport.requests.Request())
        
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {creds.token}",
        }
        
        payload = {
            "userId": user.uid,
            "userIdValidationState": user_id_validation_state,
            "consentNonce": consent_nonce,
        }
        
        print(f"[OAUTH] Calling FinalizeCredentials via HTTP POST to: {url}")
        async with httpx.AsyncClient() as client:
            response = await client.post(url, json=payload, headers=headers)
            
        print(f"[OAUTH] Finalize HTTP Status: {response.status_code}, Response: {response.text}")
        
        if response.status_code != 200:
            print(f"[OAUTH] FinalizeCredentials failed! Status: {response.status_code}, Body: {response.text}")
            return HTMLResponse(f"Failed to finalize credentials: {response.text}", status_code=500)
            
    except Exception as e:
        print(f"[OAUTH] Error calling FinalizeCredentials: {e}")
        return HTMLResponse(f"Error finalizing credentials: {str(e)}", status_code=500)

    return HTMLResponse(
        """
        <html><body style="font-family: sans-serif; padding: 2rem;">
          <p>Access granted. You can close this window and return to the chat.</p>
          <script>
            try {
              // Use BroadcastChannel to communicate back to the main window.
              // This works even if window.opener was severed by cross-origin hops.
              const bc = new BroadcastChannel('oauth-channel');
              bc.postMessage('oauth-complete');
            } catch (err) {
              console.error('Failed to post message via BroadcastChannel:', err);
            }
            // Close the popup window automatically
            window.close();
          </script>
        </body></html>
        """
    )
