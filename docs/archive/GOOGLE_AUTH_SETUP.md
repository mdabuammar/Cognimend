# Google OAuth Setup Guide for Cognimend

This guide explains how to configure Google OAuth 2.0 sign-in for Cognimend.

> ⚠️ **Important:** Completing Google OAuth setup is a manual step requiring access to Google Cloud Console. The system works fully without it — users can still sign up and log in with email/password.

---

## Step 1: Create a Google Cloud Project

1. Go to [https://console.cloud.google.com/](https://console.cloud.google.com/)
2. Click **"New Project"** in the top navigation bar
3. Enter a project name: `Cognimend` (or any name you prefer)
4. Click **"Create"**

---

## Step 2: Enable the OAuth Consent Screen

1. In the left sidebar, navigate to **APIs & Services → OAuth consent screen**
2. Choose **External** (for public users) or **Internal** (for org-only use)
3. Fill in the required fields:
   - **App name**: `Cognimend`
   - **User support email**: your email address
   - **Developer contact information**: your email address
4. Click **"Save and Continue"**
5. On the **Scopes** page, click **"Add or Remove Scopes"** and add:
   - `openid`
   - `email`
   - `profile`
6. Click **"Save and Continue"** through the remaining steps

---

## Step 3: Create OAuth 2.0 Credentials

1. Navigate to **APIs & Services → Credentials**
2. Click **"+ CREATE CREDENTIALS"** → **"OAuth Client ID"**
3. Choose **Application type**: `Web application`
4. Set **Name**: `Cognimend Web Client`

### Authorized JavaScript Origins

Add the following (adjust for your production domain):

```
http://localhost:8080
http://localhost:5173
https://yourdomain.com          # Production
```

### Authorized Redirect URIs

Add the following callback URLs:

```
http://localhost:8000/auth/google/callback       # Local development (direct)
http://localhost:8007/auth/google/callback       # Local via Gateway
https://api.yourdomain.com/auth/google/callback  # Production
```

5. Click **"Create"**
6. A dialog will show your **Client ID** and **Client Secret** — copy both securely

---

## Step 4: Configure Environment Variables

Add these to your `backend/.env` file:

```env
# Google OAuth
GOOGLE_CLIENT_ID=123456789-abcdefghijklmnop.apps.googleusercontent.com
GOOGLE_CLIENT_SECRET=GOCSPX-your_client_secret_here
GOOGLE_REDIRECT_URI=http://localhost:8000/auth/google/callback

# Frontend URL (must match Authorized JavaScript Origins)
FRONTEND_URL=http://localhost:8080
```

For **production**, update these accordingly:

```env
GOOGLE_CLIENT_ID=<your-prod-client-id>
GOOGLE_CLIENT_SECRET=<your-prod-client-secret>
GOOGLE_REDIRECT_URI=https://api.yourdomain.com/auth/google/callback
FRONTEND_URL=https://yourdomain.com
```

---

## Step 5: Test the OAuth Flow

1. Start your backend with `docker compose up -d`
2. Open the frontend at `http://localhost:8080`
3. Click **"Continue with Google"** on the Login page
4. You will be redirected to `GET /auth/google/start` on the auth service
5. After Google authentication, you will be redirected to `/auth/google/callback`
6. The auth service exchanges the code, creates/finds the user, and redirects to:
   ```
   http://localhost:8080/auth/callback?access_token=...&refresh_token=...&is_new=true
   ```
7. The frontend `AuthCallbackPage` reads the tokens and stores them in localStorage

---

## Local Development Callback

```
http://localhost:8000/auth/google/callback
```

This works when the auth service runs directly on port 8000 (not through the gateway).

---

## Production Callback

```
https://api.yourdomain.com/auth/google/callback
```

Ensure this matches exactly what is registered in the Google Cloud Console.

---

## 🔒 Security Notes

1. **Google Login ≠ Google Drive Access**  
   Signing in with Google only grants Cognimend access to your name, email, and profile picture. It does **not** grant access to Google Drive, Gmail, Docs, or any other Google services.

2. **Scopes requested**: Only `openid`, `email`, and `profile` — the minimum required for authentication.

3. **Tokens are stored server-side**: The Google access token returned during OAuth is used once to retrieve user information, then discarded. Cognimend issues its own JWT tokens.

4. **State parameter**: The current implementation generates a state token for CSRF protection. In production, store this in Redis with a short TTL and verify it on callback.

5. **ID Token verification**: For production deployments, use the [`google-auth`](https://pypi.org/project/google-auth/) Python library to verify the ID token signature rather than trusting the decoded payload.

   ```python
   from google.oauth2 import id_token
   from google.auth.transport import requests as google_requests
   
   info = id_token.verify_oauth2_token(
       id_token_str, google_requests.Request(), GOOGLE_CLIENT_ID
   )
   ```

6. **Never commit credentials**: Keep `GOOGLE_CLIENT_SECRET` in `.env` and ensure `.env` is in `.gitignore`.

---

## Troubleshooting

| Error | Cause | Fix |
|-------|-------|-----|
| `redirect_uri_mismatch` | Redirect URI not registered | Add exact URI to Google Console |
| `invalid_client` | Wrong Client ID or Secret | Double-check env vars |
| `Google OAuth is not configured` | Missing env vars | Set `GOOGLE_CLIENT_ID` in `.env` |
| `email not verified` | Google account has unverified email | Use a verified Google account |
