# Deployment Runbook

## Current Local App

Local URL:

```text
http://127.0.0.1:5174/
```

This passport autofill build is designed to run on the same computer as the browser it controls.

## Recommended Low-Cost Architecture

- Frontend/backend: local machine for the demo and browser-control workflow.
- AI extraction: Gemini API key with `gemini-3.5-flash`.
- Browser portal fill: local browser automation running on the same computer as the user.

The web app alone cannot control another person's browser from a remote server. For portal autofill without an extension, the app/backend must run on the user's own computer, or you must ship a small desktop/local agent that opens the user's browser.

## Environment Variables

Backend:

```text
GEMINI_API_KEY=your_key_here
GEMINI_MODEL=gemini-3.5-flash
ALLOWED_ORIGINS=http://127.0.0.1:5174,http://localhost:5174
GEMINI_REQUESTS_PER_MINUTE=15
```

Frontend:

```text
VITE_API_BASE_URL=http://127.0.0.1:8000
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

1. User opens the local app.
2. User uploads one or more passport source photos/PDFs.
3. Gemini extracts one passport applicant profile.
4. User reviews fields.
5. User clicks `Open & Autofill` or enters a portal URL.
6. The local app opens the portal in a controlled browser profile.
7. User handles login/CAPTCHA/OTP manually.
8. The app fills safe text fields, selects, gender/application tick controls, and DOB/date widgets when the real form appears.
9. User reviews and submits manually.

## Do Not Automate

- CAPTCHA
- OTP
- Password/login
- Payment card details
- Final submit
- Any government identity verification challenge
