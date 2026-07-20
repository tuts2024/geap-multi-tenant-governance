# Full setup walkthrough

One linear sequence from a fresh clone to a working local demo. This pulls
together `agent/README.md` and `frontend/README.md` into the actual order
you'll run things. Each step gives commands for **Linux/Mac (bash)** and
**Windows (PowerShell)** side by side - use whichever matches your machine.

On Windows, the `.sh` scripts in this repo (`setup/01...sh` etc.) need
**Git Bash** (ships with Git for Windows) or **WSL** - PowerShell can't run
them directly. Steps that run a `.sh` file say so explicitly; open Git Bash
for those specific steps even if you're doing everything else in
PowerShell.

## Prerequisites

```bash
git --version
python3 --version          # 3.11+ recommended
gcloud --version
```
```powershell
git --version
python --version          # 3.11+ recommended
gcloud --version
```

Missing `gcloud`? https://cloud.google.com/sdk/docs/install, then `gcloud init`.

## Step 0 - Authenticate

Same command set on both OSes:

```bash
gcloud auth login
gcloud config set project YOUR_PROJECT_ID
gcloud auth application-default login
```

The last command lets local Python (Firebase Admin SDK, the deploy script)
authenticate without a key file.

## Step 1 - Bootstrap the project

**Linux/Mac, or Windows in Git Bash:**
```bash
cd agent
export PROJECT_ID="your-gcp-project-id"
export LOCATION="us-central1"
export STAGING_BUCKET="your-gcp-project-id-agent-staging"

bash setup/01_bootstrap_project.sh
```

Enables required APIs, creates the staging bucket, creates the agent's own
service account.

## Step 2 - Register the Drive OAuth client (manual, browser)

No OS difference. Follow `agent/setup/02_create_oauth_clients.md`:

1. Cloud Console -> APIs & Services -> Credentials -> Create Credentials ->
   OAuth client ID
2. Consent screen: app name "Contract Analyst Agent", scope
   `drive.readonly`, add your test-user emails (Customer A / Customer B)
3. Application type: Web application
4. Authorized redirect URI: `http://localhost:8080/oauth/validateUserId`
   for local testing (swap for your real domain later)
5. Save the Client ID and Client secret

## Step 3 - Create Agent Identity auth providers

Same commands on both OSes (Git Bash on Windows):

```bash
export ORGANIZATION_ID="your-org-id"          # gcloud organizations list
export GOOGLE_DRIVE_CLIENT_ID="paste-from-step-2"
export GOOGLE_DRIVE_CLIENT_SECRET="paste-from-step-2"
export CONTINUE_URI="http://localhost:8080/oauth/validateUserId"

bash setup/03_create_auth_providers.sh
```

`gcloud alpha` not found? `gcloud components install alpha`, then retry.

Copy any redirect URI this prints - you may need to register it back in
the Google OAuth client from step 2, depending on how the connector proxies
the redirect.

## Step 4 - Bind auth providers to the agent's tools

```bash
bash setup/04_create_registry_bindings.sh
```

## Step 5 - Deploy the agent

**Linux/Mac:**
```bash
pip install -r requirements.txt --break-system-packages   # drop the flag if using a venv

export GOOGLE_CLOUD_PROJECT="your-gcp-project-id"
export GOOGLE_CLOUD_LOCATION="us-central1"
export STAGING_BUCKET="gs://your-gcp-project-id-agent-staging"
export OAUTH_CONTINUE_URI="http://localhost:8080/oauth/validateUserId"

python3 setup/05_deploy_agent.py
```

**Windows (PowerShell):**
```powershell
pip install -r requirements.txt

$env:GOOGLE_CLOUD_PROJECT = "your-gcp-project-id"
$env:GOOGLE_CLOUD_LOCATION = "us-central1"
$env:STAGING_BUCKET = "gs://your-gcp-project-id-agent-staging"
$env:OAUTH_CONTINUE_URI = "http://localhost:8080/oauth/validateUserId"

python setup/05_deploy_agent.py
```

Copy the **reasoning engine ID** from the output - needed again in step 6
and step 8.

### Step 5a - Apply Agent Gateway (Egress)
If you are using an Agent Gateway for egress isolation, update your agent with the gateway configuration:

```bash
python setup/05_update_agent_gateway.py
```
*Note: Ensure the script targets your new Reasoning Engine ID and correct Gateway path.*


## Step 6 - Re-run step 3 to grant the deployed agent access

```bash
export REASONING_ENGINE_ID="paste-from-step-5-output"
bash setup/03_create_auth_providers.sh
```

This grants the *specific deployed agent* IAM access to the auth
providers - skipped automatically the first time since the agent didn't
exist yet.

## Step 7 - Enable Firebase Auth (manual, browser)

No OS difference. Follow `frontend/setup/01_enable_firebase.md`:

1. https://console.firebase.google.com/ -> Add project -> use your
   *existing* GCP project
2. Build -> Authentication -> Sign-in method -> enable Google
3. Project settings -> General -> Your apps -> Add app -> Web
4. Copy `apiKey`, `authDomain`, `projectId`, `appId`

### Step 7a - Populate User Configurations in Datastore
The agent relies on Google Cloud Datastore to look up tenant configurations and authentication strategies (DWD vs 3LO) for each user.

```bash
python setup_user_configs.py
```
*Note: Edit `setup_user_configs.py` before running to map your specific test users/Firebase UIDs to the desired strategies.*


## Step 8 - Configure and run the frontend

**Linux/Mac:**
```bash
cd ../frontend
pip install -r requirements.txt --break-system-packages   # drop the flag if using a venv
cp .env.example .env
nano .env   # or vim, or any editor
```

Fill in (same on both OSes):

```
GOOGLE_CLOUD_PROJECT=your-gcp-project-id
GOOGLE_CLOUD_LOCATION=us-central1
AGENT_ENGINE_RESOURCE_NAME=projects/.../locations/us-central1/reasoningEngines/...
FIREBASE_API_KEY=...
FIREBASE_AUTH_DOMAIN=your-project.firebaseapp.com
FIREBASE_PROJECT_ID=your-gcp-project-id
FIREBASE_APP_ID=...
APP_BASE_URL=http://localhost:8080
```

Load it and run:

```bash
export $(grep -v '^#' .env | xargs)
uvicorn app.main:app --reload --port 8080
```

**Windows (PowerShell):**
```powershell
cd ..\frontend
pip install -r requirements.txt
copy .env.example .env
notepad .env
```

Fill in the same values as above, then load and run - PowerShell doesn't
auto-load `.env` files, so do this manually each session:

```powershell
Get-Content .env | ForEach-Object {
    if ($_ -match '^\s*([^#][^=]*)=(.*)$') {
        [System.Environment]::SetEnvironmentVariable($matches[1].Trim(), $matches[2].Trim())
    }
}
uvicorn app.main:app --reload --port 8080
```

(Alternative for either OS: `pip install python-dotenv` and load it inside
`app/main.py` if you'll restart often.)

## Step 9 - Grant yourself Operator access

New terminal, same env vars loaded (re-run the export/load step there too):

**Linux/Mac:**
```bash
python3 setup/02_set_operator_claim.py your-email@gmail.com
```

**Windows:**
```powershell
python setup/02_set_operator_claim.py your-email@gmail.com
```

## Step 10 - Test it

1. Open `http://localhost:8080/login`
2. Sign in as the email you just granted Operator to -> lands on `/admin`
3. Incognito/private window, sign in as a *different* Google account (no
   claim) -> lands on `/chat`
4. As that account: Connect Google Drive, complete consent, ask about a
   contract in that account's Drive

Step 10.4 is flagged as unverified in `frontend/README.md` ("known gaps") -
if the popup flow doesn't resolve cleanly end-to-end, that's the known
stub, not a setup mistake.

## Beyond localhost

> [!WARNING]
> Accessing the site via a direct IP address or VM hostname (e.g. when hosting on a remote VM) will cause Firebase Authentication to fail with an `auth/unauthorized-domain` error. Always access the page via `http://localhost:8080`. If you are running the server on a remote VM, set up SSH port forwarding:
> `ssh -L 8080:localhost:8080 -L 8082:localhost:8082 ntuteja@your-vm-ip`

`http://localhost:8080` only works for local testing. For a real demo URL,
deploy the frontend to Cloud Run and:
- update the OAuth client's authorized redirect URI (step 2) to the Cloud
  Run HTTPS URL
- update `CONTINUE_URI` / `OAUTH_CONTINUE_URI` (steps 3, 5, 6) to match
- update `APP_BASE_URL` in `.env` (step 8)

Not yet scripted in this repo - ask if you want a Cloud Run deploy script
added.
