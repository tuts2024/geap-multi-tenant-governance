"""
Customer-facing chat routes.

GET  /chat       -> serves the chat UI (also surfaces a Drive connect button)
POST /api/chat   -> proxies a message to the deployed agent, scoped to the
                    CURRENT verified user only

Every call here goes through Depends(get_current_user) - there is no path
in this router that accepts a customer/tenant identifier from the request
body. The only identity in play is the one FastAPI resolved from the
session cookie.
"""

import json

from fastapi import APIRouter, Depends, Request
from fastapi.responses import StreamingResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel

from ..agent_client import ask_agent
from ..auth import CurrentUser, get_current_user
from .. import config

import httpx
import google.auth
import google.auth.transport.requests

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")


@router.get("/chat")
async def chat_page(request: Request, user: CurrentUser = Depends(get_current_user)):
    return templates.TemplateResponse(
        request,
        "chat.html",
        {"user_email": user.email},
    )


@router.get("/api/connection_status")
async def check_connection_status(user: CurrentUser = Depends(get_current_user)):
    """Checks if the Google Drive connection is already authorized for the current user."""
    try:
        creds, _ = google.auth.default()
        creds.refresh(google.auth.transport.requests.Request())
        print(f"[CONNECTION_CHECK] Frontend Identity Email: {getattr(creds, 'service_account_email', None) or getattr(creds, 'signer_email', None) or 'unknown'}")
        
        url = f"https://iamconnectorcredentials.googleapis.com/v1alpha/projects/{config.PROJECT_ID}/locations/us-central1/connectors/google-drive-3lo/credentials:retrieve"
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {creds.token}",
        }
        payload = {
            "userId": user.uid,
            "continueUri": "http://localhost:8080/oauth/validateUserId",
            "scopes": ["https://www.googleapis.com/auth/drive.readonly"],
        }
        
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(url, json=payload, headers=headers)
            
        print(f"[CONNECTION_CHECK] Drive response: {response.status_code} - {response.text}")
        if response.status_code == 200:
            data = response.json()
            if data.get("done") is True or "response" in data:
                return {"authorized": True}
                
        return {"authorized": False}
    except Exception as e:
        print("[CONNECTION_CHECK] Error checking connection status:")
        import traceback
        traceback.print_exc()
        return {"authorized": False}


@router.get("/api/spotify_connection_status")
async def check_spotify_connection_status(user: CurrentUser = Depends(get_current_user)):
    """Checks if the Spotify connection is already authorized for the current user."""
    try:
        creds, _ = google.auth.default()
        creds.refresh(google.auth.transport.requests.Request())
        
        url = f"https://iamconnectorcredentials.googleapis.com/v1alpha/projects/{config.PROJECT_ID}/locations/us-central1/connectors/spotify-3lo-connector/credentials:retrieve"
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {creds.token}",
        }
        payload = {
            "userId": user.uid,
            "continueUri": "http://localhost:8080/oauth/validateUserId",
            "scopes": ["playlist-read-private"],
        }
        
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(url, json=payload, headers=headers)
            
        if response.status_code == 200:
            data = response.json()
            if data.get("done") is True or "response" in data:
                return {"authorized": True}
                
        return {"authorized": False}
    except Exception as e:
        print("[CONNECTION_CHECK] Error checking Spotify connection status:")
        import traceback
        traceback.print_exc()
        return {"authorized": False}


@router.get("/api/confluence_connection_status")
async def check_confluence_connection_status(user: CurrentUser = Depends(get_current_user)):
    """Checks if the Confluence connection is already authorized for the current user."""
    try:
        creds, _ = google.auth.default()
        creds.refresh(google.auth.transport.requests.Request())
        
        url = f"https://iamconnectorcredentials.googleapis.com/v1alpha/projects/{config.PROJECT_ID}/locations/us-central1/connectors/confluence-3lo/credentials:retrieve"
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {creds.token}",
        }
        payload = {
            "userId": user.uid,
            "continueUri": "http://localhost:8080/oauth/validateUserId",
            "scopes": [
                "read:confluence-content.summary",
                "read:confluence-content.all",
                "read:confluence-space.summary",
                "search:confluence",
                "offline_access",
                "read:page:confluence"
            ],
        }
        
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(url, json=payload, headers=headers)
            
        if response.status_code == 200:
            data = response.json()
            if data.get("done") is True or "response" in data:
                return {"authorized": True}
                
        return {"authorized": False}
    except Exception as e:
        print("[CONNECTION_CHECK] Error checking Confluence connection status:")
        import traceback
        traceback.print_exc()
        return {"authorized": False}

@router.post("/api/disconnect/{connector_type}")
async def disconnect_connector(connector_type: str, user: CurrentUser = Depends(get_current_user)):
    """Revokes authorization for a specific connector."""
    connector_map = {
        "drive": f"projects/{config.PROJECT_ID}/locations/us-central1/connectors/google-drive-3lo",
        "spotify": f"projects/{config.PROJECT_ID}/locations/us-central1/connectors/spotify-3lo-connector",
        "confluence": f"projects/{config.PROJECT_ID}/locations/us-central1/connectors/confluence-3lo",
    }
    
    if connector_type not in connector_map:
        return {"success": False, "error": "Invalid connector type"}
        
    connector_name = connector_map[connector_type]
    
    try:
        creds, _ = google.auth.default()
        creds.refresh(google.auth.transport.requests.Request())
        
        # Using the URL pattern from auth_utils.py
        url = f"https://iamconnectors.googleapis.com/v1alpha/{connector_name}:revokeAuthorization"
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {creds.token}",
        }
        payload = {
            "userId": user.uid,
        }
        
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(url, json=payload, headers=headers)
            
        if response.status_code == 200:
            return {"success": True}
            
        return {"success": False, "error": f"Failed to revoke: {response.status_code} - {response.text}"}
    except Exception as e:
        print(f"[DISCONNECT] Error revoking {connector_type}: {e}")
        return {"success": False, "error": str(e)}

class ChatMessage(BaseModel):
    message: str
    session_id: str | None = None
    agent_urn: str | None = None


@router.post("/api/chat")
async def post_chat(
    body: ChatMessage,
    user: CurrentUser = Depends(get_current_user),
):
    """Streams the agent's response back to the browser as newline-delimited JSON.

    `user` is injected by FastAPI from the verified session cookie - it is
    NOT constructed from anything in `body`. This is the structural
    enforcement point for tenant isolation on the frontend side: even if a
    malicious client sent {"user_id": "customerB-bob"} in the request body,
    there's no code path here that reads it.
    """
    print(f"[CHAT] Query from user.uid={user.uid}, email={user.email}, message='{body.message}', agent_urn='{body.agent_urn}'")

    # Prefix the message with the selected agent URN so the Vertex Reasoning Engine intercepts and maps it dynamically
    full_message = f"[agent_urn:{body.agent_urn}] {body.message}" if body.agent_urn else body.message

    async def event_stream():
        async for event in ask_agent(user, full_message, body.session_id, agent_urn=body.agent_urn):
            yield json.dumps(event) + "\n"

    return StreamingResponse(event_stream(), media_type="application/x-ndjson")
