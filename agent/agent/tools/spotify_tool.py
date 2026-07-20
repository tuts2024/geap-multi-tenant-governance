import os
import httpx
from google.adk.auth.auth_tool import AuthConfig
from google.adk.auth.auth_credential import AuthCredential
from google.adk.integrations.agent_identity import GcpAuthProviderScheme
from google.adk.tools import ToolContext, FunctionTool
from .auth_utils import get_connector_credential, revoke_connector_authorization
from google.adk.integrations.agent_registry import AgentRegistry

from .. import config

# Resolve Spotify Base URL using Agent Registry if available, otherwise fallback
SPOTIFY_BASE_URL = "https://api.spotify.com/v1"
try:
    registry = AgentRegistry(project_id=config.PROJECT_ID, location="global")
    spotify_endpoint = registry.get_endpoint(
        f"projects/{config.PROJECT_ID}/locations/global/endpoints/{config.SPOTIFY_ENDPOINT_ID}"
    )
    for interface in spotify_endpoint.get("interfaces", []):
        if interface.get("protocolBinding") == "HTTP_JSON":
            SPOTIFY_BASE_URL = interface.get("url")
            break
except Exception as e:
    print(f"[SPOTIFY_TOOL] Warning resolving Spotify endpoint from registry: {e}. Using fallback URL.")

_spotify_auth_scheme = GcpAuthProviderScheme(
    name=config.SPOTIFY_3LO_AUTH_PROVIDER,
    scopes=["playlist-read-private"],
    continue_uri=config.OAUTH_CONTINUE_URI,
)

async def spotify_get_playlists(
    tool_context: ToolContext,
) -> str | list:
    """Fetches the current user's private playlists on Spotify.
    
    Returns:
        A list of dicts with name, public status, and total tracks, or an error string.
    """
    print(f"DEBUG_TOOL_AUTH: spotify_get_playlists", flush=True)
    try:
        auth_resp = await get_connector_credential(tool_context, _spotify_auth_scheme)
        print(f"DEBUG_TOOL_AUTH: spotify_get_playlists: auth_resp={auth_resp}", flush=True)
        if not auth_resp or not hasattr(auth_resp, "http") or not auth_resp.http or not auth_resp.http.credentials or not auth_resp.http.credentials.token:
            print("[SPOTIFY_TOOL] Auth response token is missing. Requesting credentials...", flush=True)
            auth_config = AuthConfig(
                auth_scheme=_spotify_auth_scheme,
                raw_auth_credential=auth_resp,
                exchanged_auth_credential=auth_resp,
            )
            tool_context.request_credential(auth_config)
            return {"error": "Spotify access not yet authorized for this user."}
        access_token = auth_resp.http.credentials.token
        scheme = auth_resp.http.scheme or "Bearer"
    except Exception as e:
        print(f"[SPOTIFY_TOOL] Failed to retrieve auth token: {e}. Requesting credentials...", flush=True)
        auth_resp_err = None
        try:
            auth_resp_err = await get_connector_credential(tool_context, _spotify_auth_scheme)
        except Exception:
            pass
        auth_config = AuthConfig(
            auth_scheme=_spotify_auth_scheme,
            raw_auth_credential=auth_resp_err,
            exchanged_auth_credential=auth_resp_err,
        )
        tool_context.request_credential(auth_config)
        return {"error": "Spotify access not yet authorized for this user. Please authorize."}

    headers = {
        "Authorization": f"{scheme.title()} {access_token}"
    }

    async with httpx.AsyncClient() as client:
        response = await client.get(
            f"{SPOTIFY_BASE_URL}/me/playlists",
            headers=headers,
            params={"limit": 10},
        )

        if response.status_code in (401, 403):
            print(f"[SPOTIFY_TOOL] Spotify token unauthorized (status={response.status_code}). Triggering re-authentication!", flush=True)
            await revoke_connector_authorization(tool_context, _spotify_auth_scheme)
            auth_resp_err = None
            try:
                auth_resp_err = await get_connector_credential(tool_context, _spotify_auth_scheme)
            except Exception:
                pass
            auth_config = AuthConfig(
                auth_scheme=_spotify_auth_scheme,
                raw_auth_credential=auth_resp_err,
                exchanged_auth_credential=auth_resp_err,
            )
            tool_context.request_credential(auth_config)
            return {"error": "Spotify token expired or revoked. Please re-authenticate."}
        elif response.status_code != 200:
            return f"Error from Spotify API: {response.status_code} - {response.text}"

        data = response.json()
        items = data.get("items", [])

        if not items:
            return "No playlists found for the current user."

        return [
            {
                "name": item.get("name"),
                "public": item.get("public"),
                "total_tracks": item.get("tracks", {}).get("total"),
            }
            for item in items
            if item
        ]

def build_spotify_tools() -> list[FunctionTool]:
    """Wraps the Spotify functions as standard ADK tools."""
    return [
        FunctionTool(func=spotify_get_playlists),
    ]
