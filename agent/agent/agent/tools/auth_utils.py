import google.auth
from google.auth.transport.requests import Request
from google.adk.auth.auth_credential import AuthCredential, OAuth2Auth, AuthCredentialTypes, HttpAuth, HttpCredentials
from google.adk.auth.auth_tool import AuthConfig
import httpx
import os
import time
import json

import urllib.parse
from .. import config

async def get_connector_credential(tool_context, auth_scheme) -> AuthCredential | None:
    """Helper to retrieve credentials directly from the v1alpha Agent Identity Connectors API,
    supporting both local and remote Reasoning Engine runtimes.
    """
    user_id = tool_context.session.user_id if hasattr(tool_context, "session") and tool_context.session else "user"
    print(f"DEBUG_USER_ID: {user_id}", flush=True)
    
    # Google Drive / Workspace Auth Handler
    if "drive" in auth_scheme.name or "google" in auth_scheme.name:
        # Look up user config in Datastore
        auth_strategy = None
        user_email = None

        # Hardcoded User Configurations for Demo
        user_configs = {
            "HfV08Bu3n4YPXgrPvAms1i9RzwK2": {
                "email": "customera@ntuteja.altostrat.com",
                "tenant_name": "Customer A",
                "auth_strategy": "DWD",
                "dwd_service_account": "customer-a-tenant@acxiom-425322.iam.gserviceaccount.com"
            },
            "lKK7PPM62QYpdtCzrqrDcEm1aNs1": {
                "email": "customera@ntuteja.altostrat.com",
                "tenant_name": "Customer A",
                "auth_strategy": "DWD",
                "dwd_service_account": "customer-a-tenant@acxiom-425322.iam.gserviceaccount.com"
            },
            "loWmDyexCjMFhGkqV7MPZYwMnEf1": {
                "email": "customerb@ntuteja.altostrat.com",
                "tenant_name": "Customer B",
                "auth_strategy": "3LO",
                "dwd_service_account": None
            },
            "JqK87Kh2tUVntVvSurw33gdqJZj2": {
                "email": "customerb@ntuteja.altostrat.com",
                "tenant_name": "Customer B",
                "auth_strategy": "3LO",
                "dwd_service_account": None
            },
            "customera@ntuteja.altostrat.com": {
                "email": "customera@ntuteja.altostrat.com",
                "tenant_name": "Customer A",
                "auth_strategy": "DWD",
                "dwd_service_account": "customer-a-tenant@acxiom-425322.iam.gserviceaccount.com"
            },
            "customerb@ntuteja.altostrat.com": {
                "email": "customerb@ntuteja.altostrat.com",
                "tenant_name": "Customer B",
                "auth_strategy": "3LO",
                "dwd_service_account": None
            }
        }
        
        user_config = user_configs.get(user_id)
        if user_config:
            auth_strategy = user_config.get("auth_strategy")
            dwd_sa_email = user_config.get("dwd_service_account")
            user_email = user_config.get("email")
            print(f"[AUTH_UTILS] Found hardcoded user config for {user_id}: Strategy={auth_strategy}", flush=True)

        # Fallback to env var and heuristics if no DB config found
        if not auth_strategy:
            dwd_sa_email = os.environ.get("WORKSPACE_DWD_SA_EMAIL")
            if dwd_sa_email and "@" in user_id:
                auth_strategy = "DWD"
                user_email = user_id

        target_user = user_email or user_id

        if auth_strategy == "DWD" and dwd_sa_email and target_user:
            print(f"[WORKSPACE_DWD] Bypassing key files. Generating Domain-Wide Delegation via IAM Credentials API for {target_user} using service account {dwd_sa_email}...", flush=True)
            try:
                # 1. Fetch credentials for our current running environment
                source_creds, _ = google.auth.default(scopes=["https://www.googleapis.com/auth/cloud-platform"])
                source_creds.refresh(Request())
                
                # 2. Construct JWT claim set
                now = int(time.time())
                payload = {
                    "iss": dwd_sa_email,
                    "sub": target_user,
                    "scope": "https://www.googleapis.com/auth/drive.readonly",
                    "aud": "https://oauth2.googleapis.com/token",
                    "exp": now + 3600,
                    "iat": now
                }
                
                # 3. Call IAM Credentials API to sign the JWT claim set
                url = f"https://iamcredentials.googleapis.com/v1/projects/-/serviceAccounts/{dwd_sa_email}:signJwt"
                req_payload = {
                    "payload": json.dumps(payload)
                }
                
                async with httpx.AsyncClient() as client:
                    sign_res = await client.post(url, json=req_payload, headers={
                        "Authorization": f"Bearer {source_creds.token}",
                        "Content-Type": "application/json"
                    })
                    
                if sign_res.status_code == 200:
                    res_data = sign_res.json()
                    signed_jwt = res_data["signedJwt"]
                    
                    # 4. Exchange signed JWT for access token
                    token_url = "https://oauth2.googleapis.com/token"
                    exchange_data = urllib.parse.urlencode({
                        "grant_type": "urn:ietf:params:oauth:grant-type:jwt-bearer",
                        "assertion": signed_jwt
                    })
                    
                    async with httpx.AsyncClient() as client:
                        token_res = await client.post(token_url, data=exchange_data, headers={
                            "Content-Type": "application/x-www-form-urlencoded"
                        })
                        
                    if token_res.status_code == 200:
                        token_data = token_res.json()
                        token_val = token_data["access_token"]
                        
                        cred = AuthCredential(auth_type=AuthCredentialTypes.HTTP)
                        cred.http = HttpAuth(
                            scheme="Bearer",
                            credentials=HttpCredentials(token=token_val),
                            additional_headers={"Authorization": f"Bearer {token_val}"}
                        )
                        print(f"[WORKSPACE_DWD] [SUCCESS] Dynamically generated delegated DwD token for Google Drive!", flush=True)
                        return cred
                    else:
                        print(f"[WORKSPACE_DWD] [ERROR] Token exchange failed: {token_res.status_code} - {token_res.text}", flush=True)
                else:
                    print(f"[WORKSPACE_DWD] [ERROR] signJwt failed: {sign_res.status_code} - {sign_res.text}", flush=True)
                    
            except Exception as e:
                import traceback
                print(f"[WORKSPACE_DWD] [ERROR] Dynamic signJwt DwD failed: {e}. Falling back to standard flow.", flush=True)
                traceback.print_exc()

    try:
        creds, _ = google.auth.default(scopes=["https://www.googleapis.com/auth/cloud-platform"])
        creds.refresh(Request())
        
        email = getattr(creds, 'service_account_email', None) or getattr(creds, 'signer_email', None) or "unknown-email"
        print(f"DEBUG_IDENTITY: class={type(creds).__name__}, email={email}", flush=True)
        
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
        
        async with httpx.AsyncClient() as client:
            res = await client.post(url, json=payload, headers=headers)
            
        print(f"[DEBUG_CONNECTOR] API Status={res.status_code}, Body={res.text}", flush=True)
        if res.status_code == 200:
            data = res.json()
            if "response" in data and "token" in data["response"]:
                token_val = data["response"]["token"]
                h_raw = data["response"].get("header", "Authorization: Bearer")
                parts = h_raw.split(":")
                h_name = parts[0].strip() if parts else "Authorization"
                scheme = parts[1].strip() if len(parts) > 1 else ("Bearer" if "Authorization" in h_name else "")
                
                cred = AuthCredential(auth_type=AuthCredentialTypes.HTTP)
                cred.http = HttpAuth(
                    scheme=scheme,
                    credentials=HttpCredentials(token=token_val),
                    additional_headers={h_name: f"{scheme} {token_val}".strip()}
                )
                return cred
            elif "metadata" in data and "uriConsentRequired" in data["metadata"]:
                meta = data["metadata"]["uriConsentRequired"]
                cred = AuthCredential(auth_type=AuthCredentialTypes.OAUTH2)
                cred.oauth2 = OAuth2Auth(
                    auth_uri=meta.get("authorizationUri", ""),
                    nonce=meta.get("consentNonce", "")
                )
                return cred
        return None
    except Exception as e:
        print(f"[CONNECTOR_HELPER] Error retrieving credential: {e}", flush=True)
        return None

async def revoke_connector_authorization(tool_context, auth_scheme) -> bool:
    """Helper to revoke connector authorization for the current user, clearing stale/revoked credentials in GCP.
    """
    user_id = tool_context.session.user_id if hasattr(tool_context, "session") and tool_context.session else "user"
    try:
        creds, _ = google.auth.default(scopes=["https://www.googleapis.com/auth/cloud-platform"])
        creds.refresh(Request())
        
        headers = {
            "Authorization": f"Bearer {creds.token}",
            "Content-Type": "application/json"
        }
        payload = {
            "userId": user_id
        }
        
        url = f"https://iamconnectors.googleapis.com/v1alpha/{auth_scheme.name}:revokeAuthorization"
        
        async with httpx.AsyncClient() as client:
            res = await client.post(url, json=payload, headers=headers)
            
        print(f"[REVOKE_CONNECTOR] API Status={res.status_code}, Body={res.text}", flush=True)
        return res.status_code == 200
    except Exception as e:
        print(f"[REVOKE_CONNECTOR] Error revoking credential: {e}", flush=True)
        return False
