# Deployment Runbook

## Current Local App

Local URL:

```text
http://127.0.0.1:5174/
```

This only works on the same computer. For real users, deploy the frontend and backend to public URLs.

## Recommended Low-Cost Architecture

- Frontend: Vercel free/hobby tier to start.
- Backend: Railway, Render, Fly.io, or any small Python host.
- AI extraction: Gemini API key.
- Browser portal fill: local browser automation running on the same computer as the user.

The web app alone cannot control another person's browser from a remote server. For portal autofill without an extension, the app/backend must run on the user's own computer, or you must ship a small desktop/local agent that opens the user's browser.

## Environment Variables

Backend:

```text
GEMINI_API_KEY=your_key_here
GEMINI_MODEL=gemini-2.5-flash
ALLOWED_ORIGINS=https://your-public-frontend-domain
GEMINI_REQUESTS_PER_MINUTE=15
```

Frontend:

```text
VITE_API_BASE_URL=https://your-public-backend-domain
```

## Deploy Frontend

The repo already has:

```text
vercel.json
```

Steps:

1. Push/upload this project to a Git provider.
2. Import it into Vercel.
3. Set `VITE_API_BASE_URL`.
4. Deploy.
5. Confirm the public frontend opens.

## Deploy Backend

The repo already has:

```text
railway.json
backend/requirements.txt
```

Steps:

1. Deploy backend using Railway or another Python host.
2. Set the backend environment variables.
3. Confirm `/api/health` works.
4. Add the frontend URL to `ALLOWED_ORIGINS`.

## Real User Flow

1. User opens the public app.
2. User uploads document.
3. User reviews fields.
4. User clicks `Open & Autofill` or enters a portal URL.
5. The local app opens the portal in a controlled browser profile.
6. User handles login/CAPTCHA/OTP manually.
7. The app fills safe fields when the real form appears.
8. User reviews and submits manually.

## Do Not Automate

- CAPTCHA
- OTP
- Password/login
- Payment card details
- Final submit
- Any government identity verification challenge
