# Step 1 (frontend): enable Firebase Auth on your GCP project

Firebase is layered on top of the same GCP project from the agent repo - you
don't need a separate project.

1. Go to **https://console.firebase.google.com/** and click **Add project**.
2. Choose **"Use an existing Google Cloud project"** and select your project
   (the same `PROJECT_ID` used in the agent repo's setup).
3. Once created, go to **Build → Authentication → Sign-in method**.
4. Enable **Google** as a sign-in provider.
5. Go to **Project settings → General**, scroll to **Your apps**, click
   **Add app → Web**. Register a nickname (e.g. "contract-analyst-frontend").
6. Copy the generated config values - you'll need these as env vars:
   ```
   FIREBASE_API_KEY=...
   FIREBASE_AUTH_DOMAIN=your-project.firebaseapp.com
   FIREBASE_PROJECT_ID=your-project-id
   FIREBASE_APP_ID=...
   ```
7. For server-side token verification, the backend uses Application Default
   Credentials - if running locally, run:
   ```
   gcloud auth application-default login
   ```
   If running on Cloud Run with a service account attached, no extra setup
   needed (grant that service account `roles/firebaseauth.admin` or
   equivalent if you hit permission errors verifying/revoking sessions).

Note: these web config values (API key, app ID) are NOT secrets - they're
sent to the browser by design and are restricted by Firebase's own
authorized-domains list, not by being kept private.
