# Multi-Tenant Contract Analyst Agent - Client Setup Guide

This repository contains a fully functional, multi-tenant Contract Analyst Agent built on Google Cloud Platform (GCP) using the Agent Development Kit (ADK) and Vertex AI Agent Engine.

The solution demonstrates robust **per-customer data isolation** using Google Cloud Agent Identity, allowing a single agent deployment to securely serve multiple customers (e.g., Customer A and Customer B) without cross-tenant data leakage.

---

## 🏗️ Architecture Overview

The solution consists of two main components:

1.  **ADK Agent (`agent/`)**: Tenant-agnostic by construction. Deployed to Vertex AI Agent Engine. It relies on Agent Identity to resolve credentials scoped to the calling session's `user_id`.
2.  **Frontend (`frontend/`)**: A FastAPI application handling Firebase Authentication, role-based routing (Operator vs. Customer), and the OAuth redirect flow.

---

## 📋 Prerequisites

Before you begin, ensure you have the following installed and configured:

*   **Google Cloud SDK (`gcloud`)**: Authenticated to your GCP Project.
*   **Python 3.11+**: Installed on your local machine.
*   **Firebase Project**: Linked to your GCP Project (for authentication).
*   **Git**: For version control.

---

## ⚙️ Configuration Variables

The following environment variables are used throughout the setup. Set them in your terminal session or a `.env` file.

| Variable | Description | Example |
| :--- | :--- | :--- |
| `GOOGLE_CLOUD_PROJECT` | Your GCP Project ID | `my-secure-agent-project` |
| `GOOGLE_CLOUD_LOCATION` | Desired region for Vertex AI | `us-central1` |
| `STAGING_BUCKET` | GCS Bucket for deployment artifacts | `gs://my-secure-agent-staging` |
| `OAUTH_CONTINUE_URI` | Frontend callback for OAuth | `http://localhost:8080/oauth/validateUserId` |
| `ORGANIZATION_ID` | Your GCP Organization ID | `1234567890` |

---

## 🚀 Step-by-Step Setup Guide

Follow these steps in order to deploy the solution in your environment.

### Step 1: Bootstrap the Project
Enable required APIs, create the staging bucket, and setup the agent's service account.

```bash
cd agent
export PROJECT_ID="YOUR_PROJECT_ID"
export LOCATION="us-central1"
export STAGING_BUCKET="YOUR_PROJECT_ID-agent-staging"

bash setup/01_bootstrap_project.sh
```

### Step 2: Register OAuth Clients (Manual)
Configure Google OAuth for Google Drive access:
1.  Go to **APIs & Services > Credentials** in Google Cloud Console.
2.  Create an **OAuth client ID** (Web application).
3.  Set Authorized Redirect URI to: `http://localhost:8080/oauth/validateUserId` (or your domain).
4.  Save the **Client ID** and **Client Secret**.

### Step 3: Create Agent Identity Auth Providers
Register the connectors with Agent Identity.

```bash
export ORGANIZATION_ID="YOUR_ORG_ID"
export GOOGLE_DRIVE_CLIENT_ID="YOUR_CLIENT_ID"
export GOOGLE_DRIVE_CLIENT_SECRET="YOUR_CLIENT_SECRET"
export CONTINUE_URI="http://localhost:8080/oauth/validateUserId"

bash setup/03_create_auth_providers.sh
```

### Step 4: Bind Auth Providers to Tools
Bind the connectors to the agent's functional endpoints.

```bash
bash setup/04_create_registry_bindings.sh
```

### Step 5: Deploy the Agent
Deploy the ADK agent to Vertex AI Agent Engine.

```bash
pip install -r requirements.txt
python setup/05_deploy_agent.py
```
*Note: Copy the **Reasoning Engine ID** from the output.*

### Step 6: Grant Agent Access to Connectors
Re-run the Auth Provider setup with the Agent's ID to grant it IAM access.

```bash
export REASONING_ENGINE_ID="YOUR_REASONING_ENGINE_ID"
bash setup/03_create_auth_providers.sh
```

### Step 7: (Optional) Apply Agent Gateway (Egress)
If using an Egress Gateway for external calls isolation:

```bash
# Update the script with your Gateway name if different
python setup/05_update_agent_gateway.py
```

### Step 8: Populate User Configurations (Datastore)
Configure which authentication strategy (DWD vs 3LO) to use per user.

> [!NOTE]
> While User Configurations are stored in Datastore, Agent Configurations (model settings, tenant overrides) are looked up from BigQuery by default to avoid potential Egress limitations. You can switch to Firestore/Datastore for agent configs by updating `agent.py`, provided your Egress Gateway or Agent Registry allows the Firestore endpoints.

```bash
# Edit setup_user_configs.py to match your test users/Firebase UIDs
python setup_user_configs.py
```

### Step 9: Configure & Run Frontend
Set up the FastAPI frontend to talk to the deployed agent.

1.  Copy `frontend/.env.example` to `frontend/.env`.
2.  Fill in your Firebase, GCP, and Agent Engine resource names.
3.  Run the frontend:

```bash
cd frontend
pip install -r requirements.txt
export $(grep -v '^#' .env | xargs)
uvicorn app.main:app --reload --port 8080
```

---

## 🔒 Security & Tenant Isolation

*   **Zero Hardcoding**: No customer credentials or tenant names are embedded in prompts.
*   **Session Binding**: Isolation is enforced at the tool layer where Agent Identity resolves credentials scoped strictly to the active session's `user_id`.
*   **Role-Based Access**: Frontend ensures only authenticated users with valid session cookies can interact with the agent.

---

## 🛠️ Troubleshooting & Common Errors

### 1. `signJwt` Failed: 403 Permission Denied
*   **Cause**: Agent Engine Service Agent lacks permission on the Tenant Service Account.
*   **Fix**: Grant `Service Account Token Creator` role to `service-<PROJECT_NUMBER>@gcp-sa-aiplatform-re.iam.gserviceaccount.com` on the tenant service account.

### 2. Token Exchange Failed: 401 Unauthorized Client
*   **Cause**: Workspace Admin has not authorized DWD scopes.
*   **Fix**: Workspace Admin must authorize the Service Account Client ID in `admin.google.com` under API Controls.

### 3. Unexpected 3LO Consent Popup (DWD Fallback)
*   **Cause**: User ID (Firebase UID) not found in Datastore `UserConfiguration`.
*   **Fix**: Verify the UID and ensure `setup_user_configs.py` has been run for that user.
