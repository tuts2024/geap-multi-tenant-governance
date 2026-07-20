"""
Google Drive tool for the contract analyst agent.

Isolation guarantee: this tool never receives a customer ID or a token as a
function argument that the model could be tricked into supplying. The
credential is resolved by the ADK auth framework from the ACTIVE SESSION's
identity, via the google-drive-3lo auth provider binding. The LLM only ever
sees document names and content - never the underlying access token.
"""

import io

import googleapiclient.discovery
import googleapiclient.http
import httplib2
import google_auth_httplib2
from google.adk.auth.auth_tool import AuthConfig
from google.adk.auth.auth_credential import AuthCredential, OAuth2Auth, AuthCredentialTypes
from google.adk.integrations.agent_identity import GcpAuthProvider, GcpAuthProviderScheme
from google.adk.auth.credential_manager import CredentialManager
from google.adk.tools import ToolContext, FunctionTool
from .auth_utils import get_connector_credential, revoke_connector_authorization

import google.auth
from google.auth.transport.requests import Request
import httpx

from .. import config

class V1AlphaGcpAuthProvider(GcpAuthProvider):
    supported_auth_schemes = (GcpAuthProviderScheme,)
    
    async def get_auth_credential(self, auth_config: AuthConfig, context: any) -> AuthCredential:
        auth_scheme = auth_config.auth_scheme
        user_id = context.user_id if context and hasattr(context, 'user_id') and context.user_id else "user"
        
        # MODEL 1: Tenant-Specific Service Account Impersonation for Google Drive
        # if "drive" in auth_scheme.name or "google" in auth_scheme.name:
        #     print(f"[MODEL_1] Generating tenant-specific 2LO credentials for Google Drive...", flush=True)
        #     tenant_sa_mapping = {
        #         "HfV08Bu3n4YPXgrPvAms1i9RzwK2": f"customer-a-tenant@{config.PROJECT_ID}.iam.gserviceaccount.com",
        #         "loWmDyexCjMFhGkqV7MPZYwMnEf1": f"customer-b-tenant@{config.PROJECT_ID}.iam.gserviceaccount.com"
        #     }
        #     target_sa = tenant_sa_mapping.get(user_id)
        #     if not target_sa:
        #         print(f"[MODEL_1] Warning: No tenant service account mapped for user {user_id}. Falling back to Customer A.", flush=True)
        #         target_sa = f"customer-a-tenant@{config.PROJECT_ID}.iam.gserviceaccount.com"
        #         
        #     try:
        #         from google.auth import impersonated_credentials
        #         from google.auth.transport.requests import Request
        #         import google.auth
        #         
        #         source_creds, _ = google.auth.default(scopes=["https://www.googleapis.com/auth/cloud-platform"])
        #         
        #         print(f"[MODEL_1] Impersonating tenant service account: {target_sa}", flush=True)
        #         target_creds = impersonated_credentials.Credentials(
        #             source_credentials=source_creds,
        #             target_principal=target_sa,
        #             target_scopes=["https://www.googleapis.com/auth/drive.readonly"],
        #             lifetime=3600
        #         )
        #         target_creds.refresh(Request())
        #         token_val = target_creds.token
        #         
        #         class DummyCred:
        #             def __init__(self, token):
        #                 self.token = token
        #         class DummyHttp:
        #             def __init__(self, token_val_in):
        #                 self.scheme = "Bearer"
        #                 self.credentials = DummyCred(token_val_in)
        #                 self.additional_headers = {"Authorization": f"Bearer {token_val_in}"}
        #                 
        #         cred = AuthCredential(auth_type=AuthCredentialTypes.OAUTH2)
        #         cred.http = DummyHttp(token_val)
        #         print(f"[MODEL_1] [SUCCESS] Successfully generated impersonated 2LO token for Google Drive!", flush=True)
        #         return cred
        #     except Exception as e:
        #         print(f"[MODEL_1] [ERROR] Failed to impersonate tenant service account: {e}", flush=True)

        # Call live GCP v1alpha Agent Identity Connectors API
        try:
            creds, _ = google.auth.default(scopes=["https://www.googleapis.com/auth/cloud-platform"])
            creds.refresh(Request())
            
            headers = {
                "Authorization": f"Bearer {creds.token}",
                "Content-Type": "application/json"
            }
            payload = {
                "userId": user_id,
                "continueUri": getattr(auth_scheme, 'continue_uri', '') or "",
                "scopes": getattr(auth_scheme, 'scopes', []) or []
            }
            
            url = f"https://iamconnectorcredentials.googleapis.com/v1alpha/{auth_scheme.name}/credentials:retrieve"
            
            print(f"DEBUG_V1ALPHA: Sending request to: {url} with payload: {payload}", flush=True)
            async with httpx.AsyncClient() as client:
                res = await client.post(url, json=payload, headers=headers)
                
            print(f"DEBUG_V1ALPHA: API Response Status={res.status_code}, Body={res.text}", flush=True)
            if res.status_code == 200:
                data = res.json()
                
                # A. Direct token resolved (2LO / API Key / Consented 3LO)
                if "response" in data and "token" in data["response"]:
                    token_val = data["response"]["token"]
                    h_raw = data["response"].get("header", "Authorization: Bearer")
                    
                    parts = h_raw.split(":")
                    h_name = parts[0].strip() if parts else "Authorization"
                    scheme = parts[1].strip() if len(parts) > 1 else ("Bearer" if "Authorization" in h_name else "")
                    
                    class DummyCred:
                        def __init__(self, token):
                            self.token = token
                    class DummyHttp:
                        def __init__(self, token, scheme_val, hdr_name):
                            self.scheme = scheme_val
                            self.credentials = DummyCred(token)
                            self.additional_headers = {hdr_name: f"{scheme_val} {token}".strip()}
                            
                    cred = AuthCredential(
                        auth_type=AuthCredentialTypes.OAUTH2
                    )
                    cred.http = DummyHttp(token_val, scheme, h_name)
                    print(f"[SUCCESS] v1alpha retrieved token flawlessly for {auth_scheme.name}!", flush=True)
                    return cred
                    
                # B. User Consent Required (3LO) or 2LO Fallback for Google Drive
                if "metadata" in data and "uriConsentRequired" in data["metadata"]:
                    meta = data["metadata"]["uriConsentRequired"]
                    print(f"[3LO] Triggering OAuth consent popup for {auth_scheme.name}", flush=True)
                    return AuthCredential(
                        auth_type=AuthCredentialTypes.OAUTH2,
                        oauth2=OAuth2Auth(
                            auth_uri=meta.get("authorizationUri", ""),
                            nonce=meta.get("consentNonce", "")
                        )
                    )
            else:
                print(f"[WARNING] v1alpha retrieve returned status {res.status_code}", flush=True)
        except Exception as e:
            import traceback
            print(f"[WARNING] v1alpha retrieval fallback: {e}", flush=True)
            traceback.print_exc()
            
        # Fallback to base SDK provider
        return await super().get_auth_credential(auth_config, context)

# Force-overwrite the registry on the remote container as soon as the tool is imported!
CredentialManager._auth_provider_registry._providers[GcpAuthProviderScheme] = V1AlphaGcpAuthProvider()

_drive_auth_scheme = GcpAuthProviderScheme(
    name=config.GOOGLE_DRIVE_PROVIDER_NAME if hasattr(config, 'GOOGLE_DRIVE_PROVIDER_NAME') else config.GOOGLE_DRIVE_AUTH_PROVIDER,
    continue_uri=config.OAUTH_CONTINUE_URI,
    scopes=["https://www.googleapis.com/auth/drive.readonly"],
)


def _drive_client(access_token: str):
    http = httplib2.Http(disable_ssl_certificate_validation=True)
    creds = _bearer_credentials(access_token)
    authed_http = google_auth_httplib2.AuthorizedHttp(creds, http)
    service = googleapiclient.discovery.build(
        "drive",
        "v3",
        http=authed_http,
    )
    return service


def _bearer_credentials(access_token: str):
    # Lightweight credentials object - googleapiclient just needs something
    # with a valid .token and .apply(); we don't refresh here because
    # Agent Identity already handed us a live, refreshed access token.
    from google.oauth2.credentials import Credentials

    return Credentials(token=access_token)


async def search_contract_documents(
    query: str,
    tool_context: ToolContext,
) -> dict:
    """Searches the logged-in customer's own Google Drive for contract documents.

    Args:
        query: Free-text search, e.g. "MSA Acme Corp" or "vendor agreement 2025".

    Returns:
        A dict with a list of matching files (id, name, mimeType, modifiedTime).
        Only files the CURRENT customer has access to in their own Drive are
        ever returned - this tool call is scoped by the resolved credential,
        not by any tenant/customer value passed in the prompt.
    """
    print(f"DEBUG_TOOL_AUTH: search_contract_documents", flush=True)
    try:
        auth_resp = await get_connector_credential(tool_context, _drive_auth_scheme)
        print(f"DEBUG_TOOL_AUTH: search_contract_documents: auth_resp={auth_resp}", flush=True)
        if not auth_resp or not hasattr(auth_resp, "http") or not auth_resp.http or not auth_resp.http.credentials or not auth_resp.http.credentials.token:
            print("[DRIVE_TOOL] Auth response token is missing. Requesting credentials...", flush=True)
            auth_config = AuthConfig(
                auth_scheme=_drive_auth_scheme,
                raw_auth_credential=auth_resp,
                exchanged_auth_credential=auth_resp,
            )
            tool_context.request_credential(auth_config)
            return {"error": "Drive access not yet authorized for this user."}
        access_token = auth_resp.http.credentials.token
    except Exception as e:
        print(f"[DRIVE_TOOL] Failed to retrieve auth token: {e}. Requesting credentials...", flush=True)
        auth_resp_err = None
        try:
            auth_resp_err = await get_connector_credential(tool_context, _drive_auth_scheme)
        except Exception:
            pass
        auth_config = AuthConfig(
            auth_scheme=_drive_auth_scheme,
            raw_auth_credential=auth_resp_err,
            exchanged_auth_credential=auth_resp_err,
        )
        tool_context.request_credential(auth_config)
        return {"error": "Drive access not yet authorized for this user. Please authorize."}

    drive = _drive_client(access_token)
    safe_query = query.replace("'", "\\'")
    try:
        results = (
            drive.files()
            .list(
                q=(
                    f"name contains '{safe_query}' and "
                    "mimeType != 'application/vnd.google-apps.folder' and trashed = false"
                ),
                fields="files(id, name, mimeType, modifiedTime)",
                pageSize=10,
            )
            .execute()
        )
        return {"files": results.get("files", [])}
    except googleapiclient.errors.HttpError as e:
        print(f"[DRIVE_TOOL] Drive API Error: status={e.resp.status}, content={e.content}", flush=True)
        if b"Egress request is not authorized" in e.content:
            print("[DRIVE_TOOL] Egress blocked by network policy.", flush=True)
            return {"error": "Network error: Egress to Google Drive is blocked by security policy (Agent Gateway/VPC)."}
        if e.resp.status in (401, 403):
            print(f"[DRIVE_TOOL] Drive token unauthorized (status={e.resp.status}). Triggering re-authentication!", flush=True)
            await revoke_connector_authorization(tool_context, _drive_auth_scheme)
            auth_resp_err = None
            try:
                auth_resp_err = await get_connector_credential(tool_context, _drive_auth_scheme)
            except Exception:
                pass
            auth_config = AuthConfig(
                auth_scheme=_drive_auth_scheme,
                raw_auth_credential=auth_resp_err,
                exchanged_auth_credential=auth_resp_err,
            )
            tool_context.request_credential(auth_config)
            return {"error": "Google Drive token expired or revoked. Please re-authenticate."}
        raise e


async def fetch_document_text(
    file_id: str,
    tool_context: ToolContext,
) -> dict:
    """Fetches the text content of a specific Drive file by ID, for analysis.

    Args:
        file_id: The Drive file ID returned by search_contract_documents.

    Returns:
        A dict with the extracted text content of the file, truncated if very long.
    """
    print(f"DEBUG_TOOL_AUTH: fetch_document_text", flush=True)
    try:
        auth_resp = await get_connector_credential(tool_context, _drive_auth_scheme)
        print(f"DEBUG_TOOL_AUTH: fetch_document_text: auth_resp={auth_resp}", flush=True)
        if not auth_resp or not hasattr(auth_resp, "http") or not auth_resp.http or not auth_resp.http.credentials or not auth_resp.http.credentials.token:
            print("[DRIVE_TOOL] Auth response token is missing. Requesting credentials...", flush=True)
            auth_config = AuthConfig(
                auth_scheme=_drive_auth_scheme,
                raw_auth_credential=auth_resp,
                exchanged_auth_credential=auth_resp,
            )
            tool_context.request_credential(auth_config)
            return {"error": "Drive access not yet authorized for this user."}
        access_token = auth_resp.http.credentials.token
    except Exception as e:
        print(f"[DRIVE_TOOL] Failed to retrieve auth token: {e}. Requesting credentials...", flush=True)
        auth_resp_err = None
        try:
            auth_resp_err = await get_connector_credential(tool_context, _drive_auth_scheme)
        except Exception:
            pass
        auth_config = AuthConfig(
            auth_scheme=_drive_auth_scheme,
            raw_auth_credential=auth_resp_err,
            exchanged_auth_credential=auth_resp_err,
        )
        tool_context.request_credential(auth_config)
        return {"error": "Drive access not yet authorized for this user. Please authorize."}

    drive = _drive_client(access_token)
    try:
        meta = drive.files().get(fileId=file_id, fields="mimeType,name").execute()
        mime_type = meta["mimeType"]

        if mime_type == "application/vnd.google-apps.document":
            request = drive.files().export_media(fileId=file_id, mimeType="text/plain")
        else:
            request = drive.files().get_media(fileId=file_id)

        buffer = io.BytesIO()
        downloader = googleapiclient.http.MediaIoBaseDownload(buffer, request)
        done = False
        while not done:
            _, done = downloader.next_chunk()

        text = buffer.getvalue().decode("utf-8", errors="ignore")
        return {"name": meta["name"], "text": text[:50_000]}
    except googleapiclient.errors.HttpError as e:
        print(f"[DRIVE_TOOL] Drive API Error: status={e.resp.status}, content={e.content}", flush=True)
        if b"Egress request is not authorized" in e.content:
            print("[DRIVE_TOOL] Egress blocked by network policy.", flush=True)
            return {"error": "Network error: Egress to Google Drive is blocked by security policy (Agent Gateway/VPC)."}
        if e.resp.status in (401, 403):
            print(f"[DRIVE_TOOL] Drive token unauthorized (status={e.resp.status}). Triggering re-authentication!", flush=True)
            await revoke_connector_authorization(tool_context, _drive_auth_scheme)
            auth_resp_err = None
            try:
                auth_resp_err = await get_connector_credential(tool_context, _drive_auth_scheme)
            except Exception:
                pass
            auth_config = AuthConfig(
                auth_scheme=_drive_auth_scheme,
                raw_auth_credential=auth_resp_err,
                exchanged_auth_credential=auth_resp_err,
            )
            tool_context.request_credential(auth_config)
            return {"error": "Google Drive token expired or revoked. Please re-authenticate."}
        raise e


def build_drive_tools() -> list[FunctionTool]:
    """Wraps the Drive functions as standard ADK tools."""
    return [
        FunctionTool(func=search_contract_documents),
        FunctionTool(func=fetch_document_text),
    ]
