# Nepal Form Autofill

[![CI](https://github.com/lekhakustav/nepal-form-autofill/actions/workflows/ci.yml/badge.svg?branch=main)](https://github.com/lekhakustav/nepal-form-autofill/actions/workflows/ci.yml)

AI-assisted local passport application autofill for Nepal ePassport workflows.

## Features

- Passport-only v1 flow for Nepal ePassport pre-enrollment.
- Multi-file upload supports Nagarikta, NID, previous passport, and supporting image/PDF files.
- Gemini document extraction uses `gemini-3.5-flash` for photos, scanned PDFs, and searchable PDFs.
- Unified passport applicant profile for review before portal fill.
- Green auto-filled fields and yellow manual fields.
- Completion progress, print, and ReportLab PDF download.
- Portal autofill mode opens a controlled local Chrome/Edge/Brave profile, fills safe visible ePassport fields, handles gender tick/radio controls and date widgets where possible, and leaves the page open for review.
- Privacy-first backend: uploaded images and PDFs are processed in memory and not saved.

## Run locally

Backend:

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn main:app --reload --host 127.0.0.1 --port 8000
```

Create `backend/.env` from `backend/.env.example` and add:

```powershell
GEMINI_API_KEY=your-google-ai-studio-key
GEMINI_MODEL=gemini-3.5-flash
```

Frontend:

```powershell
npm install
npm run dev
```

Open `http://127.0.0.1:5174` when using `npm run start:local`.

Portal autofill needs Node.js dependencies installed with `npm install` and a local Chrome, Edge, or Brave browser. It does not use a browser extension and does not click final submit buttons, CAPTCHA, OTP, password, login, or payment controls.

## Production env

Frontend on Vercel:

- `VITE_API_BASE_URL=https://your-railway-backend.up.railway.app`

Backend on Railway:

- `GEMINI_API_KEY`
- `GEMINI_MODEL=gemini-3.5-flash`
- `ALLOWED_ORIGINS=https://your-vercel-app.vercel.app`
- `GEMINI_REQUESTS_PER_MINUTE=15`

## Release workflow

The repo uses `main` as the stable branch.

1. Create a short-lived branch for a feature or fix.
2. Keep the change focused and re-run the local build before merging.
3. Merge to `main` only after the app and portal flow are verified locally.
4. Tag releases from `main` when you want a public checkpoint.

See [RELEASE_WORKFLOW.md](./RELEASE_WORKFLOW.md) for the simple branch flow.
