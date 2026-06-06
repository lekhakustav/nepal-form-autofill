# Nepal Form Autofill Backend

FastAPI service for AI scanned image/PDF document extraction, local OCR fallback, unified master-data mapping, and ReportLab PDF generation.

## Local run

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn main:app --reload --host 127.0.0.1 --port 8000
```

For best real scanned PDF/image extraction, create `backend/.env` from `backend/.env.example` and add:

```powershell
GEMINI_API_KEY=your-google-ai-studio-key
GEMINI_MODEL=gemini-2.5-flash
```

Local OCR can still be installed as backup:

```powershell
npm run install:free-ocr
```

Google Vision can also be used by setting `GOOGLE_APPLICATION_CREDENTIALS`, but it is optional. AI scan runs first when Gemini is configured.

Uploaded files are not stored permanently. Gemini document extraction uses a short-lived temporary upload to Google's API and deletes the local temporary file immediately after processing.
