# Nepal Form Autofill

React + FastAPI app that auto-fills Nepali government and institutional forms from a Nepali citizenship card or National Identity Card photo.

## Features

- Six form types: passport, driving license, bank account opening, college/university admission, voter registration, and government job application.
- Upload flow supports Nagarikta, NID, or other supporting legal document uploads as photos or PDF files.
- AI document extraction for scanned PDF/image uploads when `GEMINI_API_KEY` or `GOOGLE_API_KEY` is configured, with local OCR only as a backup.
- Google Cloud Vision OCR fallback when service-account credentials are configured.
- Unified master data object for form config mapping.
- Green auto-filled fields and yellow manual fields.
- Completion progress, print, and ReportLab PDF download.
- Portal autofill mode: paste or pick an official website URL after extraction and the app opens a controlled local Chrome/Edge/Brave profile, fills matching visible fields, and leaves the page open for review.
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

For best photo/PDF extraction, create `backend/.env` from `backend/.env.example` and add:

```powershell
GEMINI_API_KEY=your-google-ai-studio-key
GEMINI_MODEL=gemini-2.5-flash
```

Local OCR can still be installed as a backup:

```powershell
npm run install:free-ocr
```

Frontend:

```powershell
npm install
npm run dev
```

Open `http://127.0.0.1:5174` when using `npm run start:local`.

Portal autofill needs Node.js dependencies installed with `npm install` and a local Chrome, Edge, or Brave browser. It does not use a browser extension and does not click final submit buttons.

## Production env

Frontend on Vercel:

- `VITE_API_BASE_URL=https://your-railway-backend.up.railway.app`

Backend on Railway:

- `GEMINI_API_KEY` only if you want optional cloud extraction
- `GOOGLE_API_KEY` as an alternative Gemini key name
- `GEMINI_MODEL=gemini-2.5-flash`
- `GOOGLE_APPLICATION_CREDENTIALS` or Google service account credentials configured in the Railway environment
- `ALLOWED_ORIGINS=https://your-vercel-app.vercel.app`
- `GEMINI_REQUESTS_PER_MINUTE=15`
