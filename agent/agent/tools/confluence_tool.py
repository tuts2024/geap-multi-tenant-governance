import httpx
from google.adk.auth.auth_tool import AuthConfig
from google.adk.auth.auth_credential import AuthCredential
from google.adk.integrations.agent_identity import GcpAuthProviderScheme
from google.adk.tools import ToolContext, FunctionTool
from .auth_utils import get_connector_credential, revoke_connector_authorization

from .. import config
from google.adk.integrations.agent_registry import AgentRegistry

CONFLUENCE_BASE_URL = "https://api.atlassian.com" # Default
try:
    registry = AgentRegistry(project_id=config.PROJECT_ID, location="global")
    confluence_endpoint = registry.get_endpoint(
        f"projects/{config.PROJECT_ID}/locations/global/endpoints/{config.CONFLUENCE_ENDPOINT_ID}"
    )
    for interface in confluence_endpoint.get("interfaces", []):
        if interface.get("protocolBinding") == "HTTP_JSON":
            CONFLUENCE_BASE_URL = interface.get("url")
            break
except Exception as e:
    print(f"[CONFLUENCE_TOOL] Warning resolving Confluence endpoint from registry: {e}. Using fallback URL.")


_confluence_auth_scheme = GcpAuthProviderScheme(
    name=config.CONFLUENCE_AUTH_PROVIDER,
    scopes=[
        "read:confluence-content.summary",
        "read:confluence-content.all",
        "read:confluence-space.summary",
        "search:confluence",
        "offline_access",
        "read:page:confluence"
    ],
    continue_uri=config.OAUTH_CONTINUE_URI,
)

async def confluence_search_pages(
    query: str,
    tool_context: ToolContext,
) -> dict:
    """Searches Confluence wiki pages for contract details or documentation.

    Args:
        query: Search term, e.g., "termination", "NDA", or space name.
    """
    print(f"DEBUG_TOOL_AUTH: confluence_search_pages", flush=True)
    try:
        auth_resp = await get_connector_credential(tool_context, _confluence_auth_scheme)
        print(f"DEBUG_TOOL_AUTH: confluence_search_pages: auth_resp={auth_resp}", flush=True)
        if not auth_resp or not hasattr(auth_resp, "http") or not auth_resp.http or not auth_resp.http.credentials or not auth_resp.http.credentials.token:
            print("[CONFLUENCE_TOOL] Auth response token is missing. Requesting credentials...", flush=True)
            auth_config = AuthConfig(
                auth_scheme=_confluence_auth_scheme,
                raw_auth_credential=auth_resp,
                exchanged_auth_credential=auth_resp,
            )
            tool_context.request_credential(auth_config)
            return {"error": "Confluence access not yet authorized for this user."}
        access_token = auth_resp.http.credentials.token
    except Exception as e:
        import traceback
        traceback.print_exc()
        print(f"[CONFLUENCE_TOOL] Failed to retrieve auth token: {e}. Requesting credentials...", flush=True)
        auth_resp_err = None
        try:
            auth_resp_err = await get_connector_credential(tool_context, _confluence_auth_scheme)
        except Exception:
            pass
        auth_config = AuthConfig(
            auth_scheme=_confluence_auth_scheme,
            raw_auth_credential=auth_resp_err,
            exchanged_auth_credential=auth_resp_err,
        )
        tool_context.request_credential(auth_config)
        return {"error": "Confluence access not yet authorized for this user. Please authorize."}

    headers = {
        "Authorization": f"Bearer {access_token}",
        "Accept": "application/json",
    }

    async with httpx.AsyncClient() as client:
        # 1. Fetch cloudId from accessible-resources
        res = await client.get(f"{CONFLUENCE_BASE_URL}/oauth/token/accessible-resources", headers=headers)
        if res.status_code in (401, 403):
            print(f"[CONFLUENCE_TOOL] Confluence token unauthorized (status={res.status_code}). Triggering re-authentication!", flush=True)
            await revoke_connector_authorization(tool_context, _confluence_auth_scheme)
            auth_resp_err = None
            try:
                auth_resp_err = await get_connector_credential(tool_context, _confluence_auth_scheme)
            except Exception:
                pass
            auth_config = AuthConfig(
                auth_scheme=_confluence_auth_scheme,
                raw_auth_credential=auth_resp_err,
                exchanged_auth_credential=auth_resp_err,
            )
            tool_context.request_credential(auth_config)
            return {"error": "Confluence token expired or revoked. Please re-authenticate."}
        elif res.status_code != 200:
            return {"error": f"Failed to retrieve Atlassian sites: {res.status_code} - {res.text}"}
        
        resources = res.json()
        if not resources:
            return {"error": "No Atlassian sites linked to this account."}
        
        cloud_id = None
        site_name = None
        for res_item in resources:
            scopes = res_item.get("scopes", [])
            if "read:confluence-content.summary" in scopes:
                cloud_id = res_item["id"]
                site_name = res_item.get("name", "Atlassian Site")
                break
                
        if not cloud_id:
            cloud_id = resources[0]["id"]
            site_name = resources[0].get("name", "Atlassian Site")
            
        print(f"[CONFLUENCE_TOOL] Selected Cloud ID: {cloud_id} for site: {site_name}", flush=True)

        # 2. Search Confluence pages using CQL
        search_url = f"{CONFLUENCE_BASE_URL}/ex/confluence/{cloud_id}/rest/api/content/search"
        params = {
            "cql": f'text ~ "{query}"',
            "limit": 5,
        }
        
        search_res = await client.get(search_url, headers=headers, params=params)
        if search_res.status_code != 200:
            return {"error": f"Confluence search failed: {search_res.status_code} - {search_res.text}"}
            
        data = search_res.json()
        results = data.get("results", [])
        
        pages = []
        for item in results:
            pages.append({
                "id": item.get("id"),
                "title": item.get("title"),
                "type": item.get("type"),
                "url": f"https://{site_name}/wiki{item.get('_links', {}).get('webui', '')}"
            })
            
        return {"site": site_name, "pages": pages}

async def confluence_get_page_content(
    page_id: str,
    tool_context: ToolContext,
) -> dict:
    """Retrieves the full text/content of a specific Confluence wiki page.

    Args:
        page_id: The ID of the page to retrieve, e.g., "1234567".
    """
    print(f"DEBUG_TOOL_AUTH: confluence_get_page_content", flush=True)
    try:
        auth_resp = await get_connector_credential(tool_context, _confluence_auth_scheme)
        if not auth_resp or not hasattr(auth_resp, "http") or not auth_resp.http or not auth_resp.http.credentials or not auth_resp.http.credentials.token:
            print("[CONFLUENCE_TOOL] Auth response token is missing. Requesting credentials...", flush=True)
            auth_config = AuthConfig(
                auth_scheme=_confluence_auth_scheme,
                raw_auth_credential=auth_resp,
                exchanged_auth_credential=auth_resp,
            )
            tool_context.request_credential(auth_config)
            return {"error": "Confluence access not yet authorized for this user."}
        access_token = auth_resp.http.credentials.token
    except Exception as e:
        print(f"[CONFLUENCE_TOOL] Failed to retrieve auth token: {e}. Requesting credentials...", flush=True)
        auth_resp_err = None
        try:
            auth_resp_err = await get_connector_credential(tool_context, _confluence_auth_scheme)
        except Exception:
            pass
        auth_config = AuthConfig(
            auth_scheme=_confluence_auth_scheme,
            raw_auth_credential=auth_resp_err,
            exchanged_auth_credential=auth_resp_err,
        )
        tool_context.request_credential(auth_config)
        return {"error": "Confluence access not yet authorized for this user. Please authorize."}

    headers = {
        "Authorization": f"Bearer {access_token}",
        "Accept": "application/json",
    }

    async with httpx.AsyncClient() as client:
        # 1. Fetch site resources
        res = await client.get(f"{CONFLUENCE_BASE_URL}/oauth/token/accessible-resources", headers=headers)
        if res.status_code in (401, 403):
            print(f"[CONFLUENCE_TOOL] Confluence token unauthorized (status={res.status_code}). Triggering re-authentication!", flush=True)
            await revoke_connector_authorization(tool_context, _confluence_auth_scheme)
            auth_resp_err = None
            try:
                auth_resp_err = await get_connector_credential(tool_context, _confluence_auth_scheme)
            except Exception:
                pass
            auth_config = AuthConfig(
                auth_scheme=_confluence_auth_scheme,
                raw_auth_credential=auth_resp_err,
                exchanged_auth_credential=auth_resp_err,
            )
            tool_context.request_credential(auth_config)
            return {"error": "Confluence token expired or revoked. Please re-authenticate."}
        elif res.status_code != 200:
            return {"error": f"Failed to retrieve Atlassian sites: {res.status_code} - {res.text}"}
        
        resources = res.json()
        if not resources:
            return {"error": "No Atlassian sites linked to this account."}
        
        cloud_id = None
        site_name = None
        for res_item in resources:
            scopes = res_item.get("scopes", [])
            if "read:confluence-content.summary" in scopes:
                cloud_id = res_item["id"]
                site_name = res_item.get("name", "Atlassian Site")
                break
                
        if not cloud_id:
            cloud_id = resources[0]["id"]
            site_name = resources[0].get("name", "Atlassian Site")

        # 2. Retrieve Confluence page by ID using Confluence v2 REST API
        page_url = f"{CONFLUENCE_BASE_URL}/ex/confluence/{cloud_id}/api/v2/pages/{page_id}"
        params = {"body-format": "storage"}
        
        page_res = await client.get(page_url, headers=headers, params=params)
        if page_res.status_code != 200:
            return {"error": f"Failed to retrieve page content: {page_res.status_code} - {page_res.text}"}
            
        page_data = page_res.json()
        title = page_data.get("title", "")
        html_content = page_data.get("body", {}).get("storage", {}).get("value", "")
        
        # Simple HTML to text converter
        import re
        clean_text = re.sub(r'<[^>]+>', '', html_content)
        clean_text = re.sub(r'\s+', ' ', clean_text).strip()
        
        return {
            "id": page_id,
            "title": title,
            "content": clean_text
        }

def build_confluence_tools() -> list[FunctionTool]:
    """Wraps Confluence search and read functions as standard ADK tools."""
    return [
        FunctionTool(func=confluence_search_pages),
        FunctionTool(func=confluence_get_page_content),
    ]
