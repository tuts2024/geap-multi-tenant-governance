# Client Setup Guide - Multi-Tenant Contract Analyst Agent

This guide walks through setting up the Contract Analyst Agent and Frontend in a fresh GCP environment.

## Prerequisites

1.  **Google Cloud Platform (GCP) Project**: You need an active GCP project.
2.  **Python 3.11+**: Installed on your local machine or deployment VM.
3.  **Google Cloud SDK (gcloud)**: Installed and authenticated.
4.  **Firebase Account**: Associated with your GCP project for authentication.

---

## Step-by-Step Setup

### 1. Environment Preparation

Clone this repository and navigate to the project root.

```bash
git clone <repository-url>
cd <repository-name>
```

Set the following environment variables in your terminal:

```bash
export PROJECT_ID="your-gcp-project-id"
export LOCATION="us-central1"
export STAGING_BUCKET="${PROJECT_ID}-agent-staging"
export ORGANIZATION_ID="your-org-id" # Run 'gcloud organizations list' to find this
```

### 2. Bootstrap GCP Project

Navigate to the `agent` directory and run the bootstrap script. This will enable required APIs, create a staging bucket, and create the agent's service account.

```bash
cd agent
bash setup/01_bootstrap_project.sh
```

### 3. Register OAuth Clients (Manual Steps)

You need to set up OAuth consent and credentials for the services the agent accesses (e.g., Google Drive, Confluence).

#### A. Google Drive OAuth
1.  Go to **APIs & Services > Credentials** in GCP Console.
2.  Click **Create Credentials > OAuth client ID**.
3.  Set up the Consent Screen if prompted (App name: "Contract Analyst Agent").
4.  Application type: **Web application**.
5.  Add Authorized redirect URI: `http://localhost:8080/oauth/validateUserId` (for local testing).
6.  Save the **Client ID** and **Client Secret**.

*(Repeat similar steps if using other 3LO providers like Confluence or Spotify, ensuring the redirect URIs match your setup).*

### 4. Create Agent Identity Connectors

Run the setup script to create the connectors (Auth Providers) in GCP. You will need the Client ID and Secret from the previous step.

```bash
export GOOGLE_DRIVE_CLIENT_ID="your-google-drive-client-id"
export GOOGLE_DRIVE_CLIENT_SECRET="your-google-drive-client-secret"
export CONTINUE_URI="http://localhost:8080/oauth/validateUserId"

bash setup/03_create_auth_providers.sh
```

> [!NOTE]
> The script currently covers `contract-analyst-self` (2LO) and `google-drive-3lo`. Ensure you add/configure other connectors (like Confluence) if required by your use case.

### 5. Bind Connectors to Agent Tools

Bind the created connectors to the specific tools the agent will use.

```bash
bash setup/04_create_registry_bindings.sh
```

### 6. Deploy the Agent (Reasoning Engine)

Deploy the ADK agent to Vertex AI Reasoning Engine.

```bash
# Create and activate a venv (recommended)
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Set deployment env vars
export GOOGLE_CLOUD_PROJECT="${PROJECT_ID}"
export GOOGLE_CLOUD_LOCATION="${LOCATION}"
export STAGING_BUCKET="gs://${STAGING_BUCKET}"
export OAUTH_CONTINUE_URI="http://localhost:8080/oauth/validateUserId"

python3 setup/05_deploy_agent.py
```

**Save the Reasoning Engine ID** printed at the end of the output.

### 7. Finalize IAM Bindings

Grant the deployed agent access to the connectors. Re-run the auth provider script with the new Reasoning Engine ID.

```bash
export REASONING_ENGINE_ID="your-reasoning-engine-id"
bash setup/03_create_auth_providers.sh
```

### 8. Database Setup (BigQuery & Datastore)

#### A. BigQuery
Ensure the following tables exist in your dataset (`egnyte_demo` or similar):
*   `agent_platform_registry`: Stores agent metadata and tenant overrides.
*   `user_configurations`: Stores user/tenant mappings and auth strategies.

You can use the helper scripts in the repository or create them manually with the required schema.

#### B. Populate Baseline Data
Run the setup script to populate tenant configurations (DWD vs 3LO) in Datastore/BigQuery.

```bash
# Edit setup_user_configs.py first to match your test users
python setup_user_configs.py
```

### 9. Frontend Setup & Run

Navigate to the `frontend` directory.

```bash
cd ../frontend
# Create venv and install requirements
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Create a `.env` file based on `.env.example`:

```bash
cp .env.example .env
```

Fill in the required fields in `.env`:
*   `GOOGLE_CLOUD_PROJECT`
*   `AGENT_ENGINE_RESOURCE_NAME` (Points to your deployed Reasoning Engine)
*   `FIREBASE_*` credentials (See `frontend/setup/01_enable_firebase.md` for Firebase setup)

Run the frontend:

```bash
export $(grep -v '^#' .env | xargs)
uvicorn app.main:app --reload --port 8080
```

---

## Known Issues / Customization

### Agent Ownership (e.g., "Grog")
When running the `sync_agent_registry.py` script to synchronize live Reasoning Engines with BigQuery, **all discovered agents are set to "Operator" owned by default**.

If you have agents created by specific tenants (e.g., "Customer A"), you may need to:
1.  Manually update the `owned_by` field in the BigQuery `agent_platform_registry` table.
2.  Modify the `sync_agent_registry.py` script to detect and preserve authorship if you rely on automatic syncing.

### Firebase Session Cookies & Local Development

> [!IMPORTANT]
> The frontend application uses **Firebase Session Cookies** for secure authentication.

*   **In Production (GCP)**: The app runs using an attached Service Account (e.g., on Cloud Run). The Firebase Admin SDK automatically picks up these credentials, and session cookie creation works seamlessly.
*   **In Local Development**: If you are running the frontend locally and have authenticated via `gcloud auth application-default login` using your **User Account**, the Firebase Admin SDK function `create_session_cookie` will fail with "Session creation failed".
    *   **Reason**: User credentials cannot sign Firebase session cookies; only Service Account credentials can.
    *   **Workaround**: To run and debug the frontend locally with full cookie support, you must use a **Service Account Key JSON file** and set the `GOOGLE_APPLICATION_CREDENTIALS` environment variable to point to it.

