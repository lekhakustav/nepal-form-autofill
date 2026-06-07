# Nepal Form Autofill Backend

FastAPI service for local passport packet extraction, passport profile mapping, portal autofill launch, and ReportLab PDF generation.

## Local run

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn main:app --reload --host 127.0.0.1 --port 8000
```

For real scanned PDF/image extraction, create `backend/.env` from `backend/.env.example` and add:

```powershell
GEMINI_API_KEY=your-google-ai-studio-key
GEMINI_MODEL=gemini-3.5-flash
```

The `/api/extract` endpoint is passport-only in this build. Send repeated `files` form-data entries plus `form_type=passport`; the backend forwards the document packet to Gemini and returns one reviewed applicant profile.

Google Vision OCR is not part of the intended flow. Uploaded files are processed in memory and are not stored permanently by this backend.

Portal autofill is a local browser flow, not a server-side submission bot. It fills safe visible fields in a local Chrome, Edge, or Brave profile and leaves login, CAPTCHA, OTP, payment, and final submit to the user.
