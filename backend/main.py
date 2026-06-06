import io
import json
import os
import re
import shutil
import subprocess
import tempfile
import time
from collections import deque
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from pypdf import PdfReader
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

try:
    from google.cloud import vision
except ImportError:  # pragma: no cover
    vision = None

try:
    import google.generativeai as genai
except ImportError:  # pragma: no cover
    genai = None

try:
    import fitz
except ImportError:  # pragma: no cover
    fitz = None

try:
    from PIL import Image, ImageOps
except ImportError:  # pragma: no cover
    Image = None
    ImageOps = None


def load_local_env() -> None:
    env_paths = [
        Path(__file__).resolve().parent.parent / ".env",
        Path(__file__).resolve().parent / ".env",
    ]
    for env_path in env_paths:
        if not env_path.exists():
            continue
        for line in env_path.read_text(encoding="utf-8").splitlines():
            stripped = line.strip()
            if not stripped or stripped.startswith("#") or "=" not in stripped:
                continue
            key, value = stripped.split("=", 1)
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            if key and key not in os.environ:
                os.environ[key] = value


load_local_env()

app = FastAPI(title="Nepal Form Autofill API")

allowed_origins = [
    origin.strip()
    for origin in os.getenv("ALLOWED_ORIGINS", "http://127.0.0.1:5173,http://localhost:5173,http://127.0.0.1:5174,http://localhost:5174").split(",")
    if origin.strip()
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_origin_regex=r"https://.*\.(ngrok-free\.app|ngrok\.app|loca\.lt|trycloudflare\.com)",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

FORM_TITLES = {
    "passport": ("Passport Application", "राहदानी आवेदन"),
    "driving_license": ("Driving License", "सवारी चालक अनुमतिपत्र"),
    "bank_account": ("Bank Account Opening", "बैंक खाता खोल्ने"),
    "admission": ("College/University Admission", "कलेज/विश्वविद्यालय भर्ना"),
    "voter_registration": ("Voter Registration", "मतदाता नामावली"),
    "government_job": ("Government Job Application", "सरकारी जागिर आवेदन"),
}

FIELD_LABELS = {
    "full_name_english": ("Full name", "पूरा नाम"),
    "full_name_nepali": ("Name in Nepali", "नेपाली नाम"),
    "date_of_birth": ("Date of birth", "जन्म मिति"),
    "gender": ("Gender", "लिङ्ग"),
    "address_district": ("District", "जिल्ला"),
    "address_municipality": ("Municipality / Rural Municipality", "पालिका"),
    "address_ward": ("Ward no.", "वडा नं."),
    "id_number": ("Citizenship / NID number", "नागरिकता / राष्ट्रिय परिचयपत्र नं."),
    "father_name": ("Father's name", "बुबाको नाम"),
    "mother_name": ("Mother's name", "आमाको नाम"),
    "grandfather_name": ("Grandfather's name", "हजुरबुबाको नाम"),
    "spouse_name": ("Spouse name", "पति/पत्नीको नाम"),
    "blood_group": ("Blood group", "रक्त समूह"),
    "issued_district": ("Issued district", "जारी जिल्ला"),
    "issued_date": ("Issued date", "जारी मिति"),
    "expiry_date": ("Expiry / valid until", "मान्य मिति"),
    "passport_type": ("Passport type", "राहदानीको किसिम"),
    "application_type": ("Application type", "आवेदनको किसिम"),
    "birth_place": ("Place of birth", "जन्म स्थान"),
    "old_passport_number": ("Previous passport no.", "पुरानो राहदानी नं."),
    "license_category": ("License category", "अनुमतिपत्र वर्ग"),
    "vehicle_type": ("Vehicle type", "सवारी साधनको किसिम"),
    "training_center": ("Training center", "प्रशिक्षण केन्द्र"),
    "bank_branch": ("Bank branch", "बैंक शाखा"),
    "account_currency": ("Currency", "मुद्रा"),
    "phone": ("Mobile number", "मोबाइल नं."),
    "email": ("Email address", "इमेल"),
    "occupation": ("Occupation", "पेशा"),
    "income_source": ("Source of income", "आय स्रोत"),
    "education_level": ("Education level", "शैक्षिक योग्यता"),
    "institution_name": ("Institution name", "संस्थाको नाम"),
    "account_type": ("Account type", "खाता प्रकार"),
    "faculty": ("Faculty", "संकाय"),
    "guardian_name": ("Guardian name", "अभिभावकको नाम"),
    "program": ("Program / Faculty", "कार्यक्रम / संकाय"),
    "level": ("Level", "तह"),
    "post_applied": ("Position applied for", "आवेदन गरिएको पद"),
    "service_group": ("Service / group", "सेवा / समूह"),
    "advertisement_number": ("Advertisement no.", "विज्ञापन नं."),
    "exam_center": ("Exam center", "परीक्षा केन्द्र"),
    "voter_area": ("Voting area", "मतदान क्षेत्र"),
    "registration_place": ("Registration place", "दर्ता स्थान"),
    "polling_place": ("Polling place", "मतदान स्थल"),
}

DETECTION_PROMPT = """Look at this raw OCR text and determine if it is from a Nepali Nagarikta (citizenship card) or a Nepali National Identity Card (NID). Citizenship cards typically contain: citizenship_number, issued_district, grandfather_name. NID cards typically contain: nid_number, a unique 11-digit ID number, smart card indicators. Return only 'CITIZENSHIP' or 'NID' as your answer."""

CITIZENSHIP_PROMPT = """The following is raw OCR text from a Nepali Nagarikta (citizenship card). Parse and return only a JSON object with: full_name_nepali, full_name_english, date_of_birth, gender, permanent_address (district, municipality, ward), citizenship_number, issued_district, issued_date, expiry_date (if visible), father_name, mother_name, grandfather_name, spouse_name (if present), blood_group (if present). Set missing fields to null. Return only JSON."""

NID_PROMPT = """The following is raw OCR text from a Nepali National Identity Card (NID). Parse and return only a JSON object with: full_name_nepali, full_name_english, date_of_birth, gender, permanent_address (district, municipality, ward), nid_number, issued_district (if visible), issued_date (if visible), expiry_date (if visible), father_name, mother_name, spouse_name (if present), blood_group (if present). Set missing fields to null. Return only JSON."""

DOCUMENT_EXTRACTION_PROMPT = """Read this Nepali ID document image or PDF visually and return only a JSON object.
Detect whether it is a Nepali Nagarikta citizenship card or a Nepali National Identity Card.
Use the exact visible values from the document whenever possible.
Focus on names, identity numbers, dates, gender, address, issued district, father/mother/grandfather names, spouse, and blood group.
If a scanned PDF is represented by page images, combine the visible data across pages.
Return this shape:
{
  "id_type": "CITIZENSHIP" or "NID",
  "full_name_nepali": string or null,
  "full_name_english": string or null,
  "date_of_birth": string or null,
  "gender": string or null,
  "permanent_address": {"district": string or null, "municipality": string or null, "ward": string or null},
  "citizenship_number": string or null,
  "nid_number": string or null,
  "issued_district": string or null,
  "issued_date": string or null,
  "expiry_date": string or null,
  "father_name": string or null,
  "mother_name": string or null,
  "grandfather_name": string or null,
  "spouse_name": string or null,
  "blood_group": string or null,
  "raw_text": string or null
}
Return only JSON. Do not invent missing values."""

gemini_requests = deque()
USAGE_LOG_PATH = Path(__file__).resolve().parent / "usage-log.json"


class PdfRequest(BaseModel):
    form_type: str
    id_type: str | None = None
    values: dict[str, Any]


class PortalAutofillRequest(BaseModel):
    portal_url: str
    values: dict[str, Any]
    wait_for_form: bool = True
    wait_timeout_ms: int = 5 * 60 * 1000
    browser_profile: str = "portal-default"


class GeminiSettingsRequest(BaseModel):
    api_key: str
    model: str | None = None


def usage_day() -> str:
    return datetime.now(timezone.utc).astimezone().strftime("%Y-%m-%d")


def default_usage() -> dict[str, Any]:
    return {
        "days": {},
        "events": [],
    }


def read_usage_log() -> dict[str, Any]:
    if not USAGE_LOG_PATH.exists():
        return default_usage()
    try:
        data = json.loads(USAGE_LOG_PATH.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            return default_usage()
        data.setdefault("days", {})
        data.setdefault("events", [])
        return data
    except (json.JSONDecodeError, OSError):
        return default_usage()


def write_usage_log(data: dict[str, Any]) -> None:
    USAGE_LOG_PATH.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def usage_bucket(data: dict[str, Any], day: str) -> dict[str, Any]:
    days = data.setdefault("days", {})
    bucket = days.setdefault(day, {})
    bucket.setdefault("ocr_scans", 0)
    bucket.setdefault("gemini_calls", 0)
    bucket.setdefault("input_tokens", 0)
    bucket.setdefault("output_tokens", 0)
    bucket.setdefault("total_tokens", 0)
    bucket.setdefault("pdf_downloads", 0)
    bucket.setdefault("portal_sessions", 0)
    bucket.setdefault("local_text_pdf_scans", 0)
    bucket.setdefault("local_ocr_scans", 0)
    bucket.setdefault("vision_scans", 0)
    bucket.setdefault("errors", 0)
    return bucket


def token_count(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def response_usage_metadata(response: Any) -> dict[str, int]:
    metadata = getattr(response, "usage_metadata", None)
    if not metadata:
        return {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0}
    input_tokens = token_count(getattr(metadata, "prompt_token_count", None))
    output_tokens = token_count(getattr(metadata, "candidates_token_count", None))
    total_tokens = token_count(getattr(metadata, "total_token_count", None)) or input_tokens + output_tokens
    return {
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "total_tokens": total_tokens,
    }


def record_usage(event_type: str, **details: Any) -> None:
    data = read_usage_log()
    day = usage_day()
    bucket = usage_bucket(data, day)
    if event_type == "ocr_scan":
        bucket["ocr_scans"] += 1
    elif event_type == "gemini_call":
        bucket["gemini_calls"] += 1
        bucket["input_tokens"] += token_count(details.get("input_tokens"))
        bucket["output_tokens"] += token_count(details.get("output_tokens"))
        bucket["total_tokens"] += token_count(details.get("total_tokens"))
    elif event_type == "pdf_download":
        bucket["pdf_downloads"] += 1
    elif event_type == "portal_session":
        bucket["portal_sessions"] += 1
    elif event_type == "local_text_pdf_scan":
        bucket["local_text_pdf_scans"] += 1
    elif event_type == "local_ocr_scan":
        bucket["local_ocr_scans"] += 1
    elif event_type == "vision_scan":
        bucket["vision_scans"] += 1
    elif event_type == "error":
        bucket["errors"] += 1

    events = data.setdefault("events", [])
    events.append({
        "at": datetime.now(timezone.utc).isoformat(),
        "type": event_type,
        "details": {key: value for key, value in details.items() if key != "api_key"},
    })
    data["events"] = events[-120:]
    write_usage_log(data)


def classify_ai_error(exc: Exception) -> str:
    message = str(exc).lower()
    if "quota" in message or "resource_exhausted" in message or "429" in message or "rate limit" in message:
        return "rate_limit"
    if "api key" in message or "permission" in message or "unauthenticated" in message:
        return "auth"
    return "unknown"


def cloud_quota_status() -> dict[str, Any]:
    gcloud_path = shutil.which("gcloud")
    project = os.getenv("GOOGLE_CLOUD_PROJECT") or os.getenv("GCLOUD_PROJECT")
    if not gcloud_path:
        return {
            "connected": False,
            "tool": "gcloud_missing",
            "project": project,
            "message": "Install and sign in to Google Cloud CLI to read Cloud Quotas from this PC.",
        }
    try:
        result = subprocess.run(
            ["gcloud", "config", "get-value", "project"],
            capture_output=True,
            text=True,
            timeout=8,
        )
        configured_project = result.stdout.strip() if result.returncode == 0 else ""
        return {
            "connected": bool(configured_project or project),
            "tool": "gcloud",
            "project": configured_project or project,
            "message": "Google Cloud CLI is available. Use Google AI Studio links for Gemini free-tier RPM/TPM/RPD, and Cloud Console for billable quotas.",
        }
    except (subprocess.SubprocessError, OSError):
        return {
            "connected": False,
            "tool": "gcloud_error",
            "project": project,
            "message": "Google Cloud CLI is installed but not responding.",
        }


def enforce_gemini_rate_limit() -> None:
    now = time.time()
    while gemini_requests and now - gemini_requests[0] > 60:
        gemini_requests.popleft()
    if len(gemini_requests) >= int(os.getenv("GEMINI_REQUESTS_PER_MINUTE", "15")):
        raise HTTPException(status_code=429, detail="Gemini rate limit reached. Please wait a minute and try again.")
    gemini_requests.append(now)


def gemini_api_key() -> str | None:
    return os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")


def google_vision_configured() -> bool:
    return bool(os.getenv("GOOGLE_APPLICATION_CREDENTIALS") or os.getenv("GOOGLE_CLOUD_PROJECT"))


def tesseract_command() -> str | None:
    configured = os.getenv("TESSERACT_CMD")
    if configured and Path(configured).exists():
        return configured
    discovered = shutil.which("tesseract")
    if discovered:
        return discovered
    for candidate in [
        r"C:\Program Files\Tesseract-OCR\tesseract.exe",
        r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
    ]:
        if Path(candidate).exists():
            return candidate
    return None


def local_ocr_available() -> bool:
    return bool(tesseract_command() or tesseract_js_available())


def tesseract_js_available() -> bool:
    root = Path(__file__).resolve().parent.parent
    return bool(
        shutil.which("node")
        and (root / "scripts" / "free-ocr.js").exists()
        and (root / "node_modules" / "tesseract.js").exists()
    )


def save_backend_env(updates: dict[str, str]) -> None:
    env_path = Path(__file__).resolve().parent / ".env"
    existing: dict[str, str] = {}
    if env_path.exists():
        for line in env_path.read_text(encoding="utf-8").splitlines():
            stripped = line.strip()
            if not stripped or stripped.startswith("#") or "=" not in stripped:
                continue
            key, value = stripped.split("=", 1)
            existing[key.strip()] = value.strip()
    existing.update({key: value for key, value in updates.items() if value is not None})
    ordered_keys = [
        "GEMINI_API_KEY",
        "GOOGLE_API_KEY",
        "GEMINI_MODEL",
        "GOOGLE_APPLICATION_CREDENTIALS",
        "ALLOWED_ORIGINS",
        "GEMINI_REQUESTS_PER_MINUTE",
        "USE_MOCK_AI",
    ]
    lines = []
    for key in ordered_keys:
        if key in existing:
            lines.append(f"{key}={existing[key]}")
    for key in sorted(set(existing) - set(ordered_keys)):
        lines.append(f"{key}={existing[key]}")
    env_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def demo_data_enabled() -> bool:
    return (
        os.getenv("USE_MOCK_AI", "").lower() == "true"
        and os.getenv("ALLOW_DEMO_DATA", "").lower() == "true"
    )


def extract_text_from_pdf(file_bytes: bytes) -> str:
    try:
        reader = PdfReader(io.BytesIO(file_bytes))
        return "\n".join(page.extract_text() or "" for page in reader.pages[:5]).strip()
    except Exception:
        return ""


def compress_image_for_ai(file_bytes: bytes) -> bytes:
    if Image is None or ImageOps is None:
        return file_bytes
    try:
        image = Image.open(io.BytesIO(file_bytes))
        image = ImageOps.exif_transpose(image).convert("RGB")
        image.thumbnail((1800, 1800))
        output = io.BytesIO()
        image.save(output, format="JPEG", quality=84, optimize=True)
        return output.getvalue()
    except Exception:
        return file_bytes


def pdf_page_images_for_ai(file_bytes: bytes) -> list[dict[str, Any]]:
    if fitz is None:
        return [{"mime_type": "application/pdf", "data": file_bytes}]
    parts: list[dict[str, Any]] = []
    pdf = None
    try:
        pdf = fitz.open(stream=file_bytes, filetype="pdf")
        for page in pdf[:3]:
            pixmap = page.get_pixmap(matrix=fitz.Matrix(1.7, 1.7), alpha=False)
            image_bytes = pixmap.tobytes("jpeg", jpg_quality=84)
            parts.append({"mime_type": "image/jpeg", "data": image_bytes})
    finally:
        if pdf is not None:
            pdf.close()
    return parts or [{"mime_type": "application/pdf", "data": file_bytes}]


def ai_document_parts(file_bytes: bytes, content_type: str) -> list[dict[str, Any]]:
    if content_type == "application/pdf":
        return pdf_page_images_for_ai(file_bytes)
    if content_type.startswith("image/"):
        return [{"mime_type": "image/jpeg", "data": compress_image_for_ai(file_bytes)}]
    return [{"mime_type": content_type or "application/octet-stream", "data": file_bytes}]


def run_tesseract(image_bytes: bytes, suffix: str) -> str:
    command = tesseract_command()
    use_tesseract_js = not command and tesseract_js_available()
    if not command and not use_tesseract_js:
        raise HTTPException(status_code=500, detail="Free local OCR is not installed. Run npm install, or install Tesseract OCR, or add optional Gemini cloud extraction.")
    temp_path = None
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as temp_file:
            temp_file.write(image_bytes)
            temp_path = temp_file.name
        languages = os.getenv("TESSERACT_LANGS", "eng+nep")
        if use_tesseract_js:
            script_path = Path(__file__).resolve().parent.parent / "scripts" / "free-ocr.js"
            result = subprocess.run(["node", str(script_path), temp_path, languages], capture_output=True, text=True, timeout=90)
        else:
            args = [command, temp_path, "stdout", "-l", languages]
            result = subprocess.run(args, capture_output=True, text=True, timeout=45)
            if result.returncode != 0 and languages != "eng":
                result = subprocess.run([command, temp_path, "stdout", "-l", "eng"], capture_output=True, text=True, timeout=45)
        if result.returncode != 0:
            raise HTTPException(status_code=502, detail=f"Free local OCR failed: {result.stderr.strip() or 'Tesseract returned no text.'}")
        return result.stdout.strip()
    except subprocess.TimeoutExpired as exc:
        raise HTTPException(status_code=504, detail="Free local OCR took too long. Try a clearer cropped image.") from exc
    finally:
        if temp_path:
            try:
                os.unlink(temp_path)
            except OSError:
                pass


def extract_text_with_local_ocr(file_bytes: bytes, content_type: str, filename: str | None = None) -> str:
    if content_type == "application/pdf":
        embedded_text = extract_text_from_pdf(file_bytes)
        if embedded_text:
            return embedded_text
        if fitz is None:
            raise HTTPException(status_code=500, detail="Free scanned-PDF OCR needs PyMuPDF installed. Run pip install -r backend/requirements.txt.")
        texts = []
        try:
            pdf = fitz.open(stream=file_bytes, filetype="pdf")
            for page in pdf[:3]:
                pixmap = page.get_pixmap(matrix=fitz.Matrix(2, 2), alpha=False)
                texts.append(run_tesseract(pixmap.tobytes("png"), ".png"))
            pdf.close()
        except HTTPException:
            raise
        except Exception as exc:
            raise HTTPException(status_code=502, detail=f"Free scanned-PDF OCR failed: {exc}") from exc
        return "\n".join(text for text in texts if text.strip()).strip()

    suffix = Path(filename or "").suffix
    if not suffix:
        suffix = ".jpg"
    return run_tesseract(file_bytes, suffix)


def gemini_model_name() -> str:
    return os.getenv("GEMINI_MODEL", "gemini-2.5-flash")


def extract_with_gemini_document(file_bytes: bytes, content_type: str, filename: str | None = None) -> dict[str, Any]:
    if demo_data_enabled():
        return {**mock_citizenship_json(), "id_type": "CITIZENSHIP", "raw_text": mock_ocr_text()}
    if genai is None:
        raise HTTPException(status_code=500, detail="Gemini SDK is not installed.")
    api_key = gemini_api_key()
    if not api_key:
        raise HTTPException(status_code=500, detail="Add GEMINI_API_KEY or GOOGLE_API_KEY to backend/.env to extract real data from scanned images and PDFs.")

    enforce_gemini_rate_limit()
    suffix = Path(filename or "").suffix
    if not suffix:
        suffix = ".pdf" if content_type == "application/pdf" else ".jpg"

    temp_path = None
    uploaded_file = None
    try:
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel(gemini_model_name())
        inline_error: Exception | None = None
        try:
            response = model.generate_content(
                [DOCUMENT_EXTRACTION_PROMPT, *ai_document_parts(file_bytes, content_type)],
                generation_config={"temperature": 0, "response_mime_type": "application/json"},
            )
            record_usage("gemini_call", model=gemini_model_name(), source="inline_document_extraction", **response_usage_metadata(response))
            extracted = parse_json_response(response.text or "")
            extracted["id_type"] = normalize_id_type(extracted.get("id_type") or heuristic_detect_id_type(extracted.get("raw_text") or ""))
            return extracted
        except HTTPException:
            raise
        except Exception as exc:
            inline_error = exc
            category = classify_ai_error(exc)
            record_usage("error", source="inline_document_extraction", category=category, message=str(exc)[:220])
            if category in {"rate_limit", "auth"}:
                raise

        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as temp_file:
            temp_file.write(file_bytes)
            temp_path = temp_file.name
        uploaded_file = genai.upload_file(temp_path, mime_type=content_type)
        while getattr(getattr(uploaded_file, "state", None), "name", "") == "PROCESSING":
            time.sleep(1)
            uploaded_file = genai.get_file(uploaded_file.name)
        if getattr(getattr(uploaded_file, "state", None), "name", "") == "FAILED":
            raise HTTPException(status_code=502, detail="Gemini could not process this uploaded file.")
        response = model.generate_content(
            [DOCUMENT_EXTRACTION_PROMPT, uploaded_file],
            generation_config={"temperature": 0, "response_mime_type": "application/json"},
        )
        record_usage("gemini_call", model=gemini_model_name(), source="document_extraction", **response_usage_metadata(response))
        extracted = parse_json_response(response.text or "")
        extracted["id_type"] = normalize_id_type(extracted.get("id_type") or heuristic_detect_id_type(extracted.get("raw_text") or ""))
        return extracted
    except HTTPException:
        raise
    except Exception as exc:
        message = str(exc).lower()
        if "quota" in message or "resource_exhausted" in message or "429" in message:
            raise HTTPException(status_code=429, detail="Gemini rate limit reached. Please wait and try again.") from exc
        raise HTTPException(status_code=502, detail=f"Gemini document extraction failed: {exc}") from exc
    finally:
        if uploaded_file is not None:
            try:
                genai.delete_file(uploaded_file.name)
            except Exception:
                pass
        if temp_path:
            try:
                os.unlink(temp_path)
            except OSError:
                pass


def extract_text_with_vision(file_bytes: bytes, content_type: str) -> str:
    if demo_data_enabled():
        return mock_ocr_text()
    if content_type == "application/pdf":
        embedded_text = extract_text_from_pdf(file_bytes)
        if embedded_text:
            return embedded_text
    if vision is None:
        raise HTTPException(status_code=500, detail="Google Vision SDK is not installed.")
    if not google_vision_configured():
        raise HTTPException(status_code=500, detail="Google Vision credentials are not configured. Add GEMINI_API_KEY for Gemini document extraction, or configure GOOGLE_APPLICATION_CREDENTIALS for Google Vision OCR.")
    try:
        client = vision.ImageAnnotatorClient()
        if content_type == "application/pdf":
            input_config = vision.InputConfig(content=file_bytes, mime_type="application/pdf")
            feature = vision.Feature(type_=vision.Feature.Type.DOCUMENT_TEXT_DETECTION)
            request = vision.AnnotateFileRequest(input_config=input_config, features=[feature], pages=[1, 2, 3])
            result = client.batch_annotate_files(requests=[request])
            texts = []
            for response in result.responses[0].responses:
                if response.error.message:
                    raise RuntimeError(response.error.message)
                if response.full_text_annotation.text:
                    texts.append(response.full_text_annotation.text)
            return "\n".join(texts)
        result = client.text_detection(image=vision.Image(content=file_bytes))
    except Exception as exc:
        message = str(exc).lower()
        if "quota" in message or "resource_exhausted" in message or "429" in message:
            raise HTTPException(status_code=429, detail="Google Vision free quota appears to be exhausted. Please try again later.")
        if "default credentials" in message or "could not automatically determine credentials" in message:
            raise HTTPException(status_code=500, detail="Google Vision credentials are not configured. Text-based PDFs can be read locally, but scanned PDFs and images need Google Vision OCR.")
        raise HTTPException(status_code=502, detail=f"Google Vision OCR failed: {exc}") from exc
    if result.error.message:
        detail = result.error.message
        if "quota" in detail.lower():
            raise HTTPException(status_code=429, detail="Google Vision free quota appears to be exhausted. Please try again later.")
        raise HTTPException(status_code=502, detail=f"Google Vision OCR failed: {detail}")
    return result.full_text_annotation.text if result.full_text_annotation else ""


def gemini_generate(prompt: str, raw_text: str) -> str:
    if demo_data_enabled():
        if "Return only 'CITIZENSHIP'" in prompt:
            return "CITIZENSHIP"
        return json.dumps(mock_citizenship_json(), ensure_ascii=False)
    if genai is None:
        raise HTTPException(status_code=500, detail="Gemini SDK is not installed.")
    api_key = gemini_api_key()
    if not api_key:
        if "Return only 'CITIZENSHIP'" in prompt:
            return heuristic_detect_id_type(raw_text)
        return json.dumps(heuristic_extract_json(raw_text, "NID" if "NID" in prompt else "CITIZENSHIP"), ensure_ascii=False)
    enforce_gemini_rate_limit()
    try:
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel(gemini_model_name())
        response = model.generate_content(f"{prompt}\n\nRAW OCR TEXT:\n{raw_text}")
        record_usage("gemini_call", model=gemini_model_name(), source="text_parse", **response_usage_metadata(response))
        return response.text.strip()
    except Exception as exc:
        message = str(exc).lower()
        if "quota" in message or "resource_exhausted" in message or "429" in message:
            raise HTTPException(status_code=429, detail="Gemini free-tier rate limit reached. Please wait and try again.")
        raise HTTPException(status_code=502, detail=f"Gemini parsing failed: {exc}") from exc


def parse_json_response(text: str) -> dict[str, Any]:
    cleaned = text.strip()
    cleaned = re.sub(r"^```(?:json)?", "", cleaned).strip()
    cleaned = re.sub(r"```$", "", cleaned).strip()
    match = re.search(r"\{.*\}", cleaned, re.S)
    if match:
        cleaned = match.group(0)
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=502, detail="Gemini returned malformed JSON.") from exc


def normalize_id_type(value: str) -> str:
    upper = value.strip().upper()
    if "NID" in upper:
        return "NID"
    if "CITIZEN" in upper:
        return "CITIZENSHIP"
    raise HTTPException(status_code=502, detail="Could not detect whether the ID is Citizenship or NID.")


def find_after_label(text: str, labels: list[str]) -> str | None:
    for label in labels:
        pattern = rf"{re.escape(label)}\s*[:：-]?\s*([^\n\r]+)"
        match = re.search(pattern, text, re.I)
        if match:
            value = match.group(1).strip(" :-\t")
            if value:
                return value[:90]
    return None


STANDARD_DIGITS = str.maketrans({
    "०": "0",
    "१": "1",
    "२": "2",
    "३": "3",
    "४": "4",
    "५": "5",
    "६": "6",
    "७": "7",
    "८": "8",
    "९": "9",
    "٠": "0",
    "١": "1",
    "٢": "2",
    "٣": "3",
    "٤": "4",
    "٥": "5",
    "٦": "6",
    "٧": "7",
    "٨": "8",
    "٩": "9",
    "۰": "0",
    "۱": "1",
    "۲": "2",
    "۳": "3",
    "۴": "4",
    "۵": "5",
    "۶": "6",
    "۷": "7",
    "۸": "8",
    "۹": "9",
})


def standard_digits(value: Any) -> Any:
    if isinstance(value, str):
        return value.translate(STANDARD_DIGITS)
    if isinstance(value, dict):
        return {key: standard_digits(item) for key, item in value.items()}
    if isinstance(value, list):
        return [standard_digits(item) for item in value]
    return value


def heuristic_detect_id_type(raw_text: str) -> str:
    upper = raw_text.upper()
    if re.search(r"\bNID\b|NATIONAL\s+IDENTITY|IDENTITY\s+NUMBER|\b\d{11}\b", upper):
        return "NID"
    return "CITIZENSHIP"


def heuristic_extract_json(raw_text: str, id_type: str) -> dict[str, Any]:
    number_match = re.search(r"\b\d{2,4}[-/]\d{1,4}[-/]\d{1,4}[-/]\d{3,8}\b|\b\d{2,4}[-/]\d{1,4}[-/]\d{3,8}\b|\b\d{11}\b", raw_text)
    dob_match = re.search(r"\b(?:19|20|20\d\d|20[5-9]\d|21\d\d)\d?[-/.]\d{1,2}[-/.]\d{1,2}\b", raw_text)
    gender = find_after_label(raw_text, ["Gender", "Sex", "लिङ्ग"])
    address_line = find_after_label(raw_text, ["Permanent Address", "Address", "ठेगाना"])
    district = find_after_label(raw_text, ["District", "जिल्ला"])
    return {
        "full_name_nepali": find_after_label(raw_text, ["नाम"]),
        "full_name_english": find_after_label(raw_text, ["Name", "Full Name"]),
        "date_of_birth": dob_match.group(0) if dob_match else find_after_label(raw_text, ["Date of Birth", "DOB", "जन्म मिति"]),
        "gender": gender,
        "permanent_address": {
            "district": district or address_line,
            "municipality": find_after_label(raw_text, ["Municipality", "पालिका"]),
            "ward": find_after_label(raw_text, ["Ward", "वडा"]),
        },
        "citizenship_number": number_match.group(0) if id_type == "CITIZENSHIP" and number_match else None,
        "nid_number": number_match.group(0) if id_type == "NID" and number_match else None,
        "issued_district": find_after_label(raw_text, ["Issued District", "Issue District", "जारी जिल्ला"]),
        "issued_date": find_after_label(raw_text, ["Issued Date", "Issue Date", "जारी मिति"]),
        "expiry_date": find_after_label(raw_text, ["Expiry Date", "Expiration Date", "Valid Until", "मान्य मिति"]),
        "father_name": find_after_label(raw_text, ["Father's Name", "Father Name", "बुबाको नाम"]),
        "mother_name": find_after_label(raw_text, ["Mother's Name", "Mother Name", "आमाको नाम"]),
        "grandfather_name": find_after_label(raw_text, ["Grandfather's Name", "Grandfather Name", "हजुरबुबाको नाम"]),
        "spouse_name": find_after_label(raw_text, ["Spouse Name", "Husband Name", "Wife Name", "पति", "पत्नी"]),
        "blood_group": find_after_label(raw_text, ["Blood Group", "रक्त समूह"]),
    }


def unified_master(id_type: str, data: dict[str, Any]) -> dict[str, Any]:
    data = standard_digits(data)
    address = data.get("permanent_address") or {}
    return standard_digits({
        "full_name_english": data.get("full_name_english"),
        "full_name_nepali": data.get("full_name_nepali"),
        "date_of_birth": data.get("date_of_birth"),
        "gender": data.get("gender"),
        "permanent_address": {
            "district": address.get("district"),
            "municipality": address.get("municipality"),
            "ward": address.get("ward"),
        },
        "citizenship_number": data.get("citizenship_number") if id_type == "CITIZENSHIP" else None,
        "nid_number": data.get("nid_number") if id_type == "NID" else None,
        "id_type": id_type,
        "issued_district": data.get("issued_district"),
        "issued_date": data.get("issued_date"),
        "expiry_date": data.get("expiry_date"),
        "father_name": data.get("father_name"),
        "mother_name": data.get("mother_name"),
        "grandfather_name": data.get("grandfather_name") if id_type == "CITIZENSHIP" else None,
        "spouse_name": data.get("spouse_name"),
        "blood_group": data.get("blood_group"),
    })


@app.get("/api/health")
def health() -> dict[str, Any]:
    google_credentials = google_vision_configured()
    gemini_key = bool(gemini_api_key())
    local_ocr = local_ocr_available()
    ocr_mode = "ai_document_extraction" if gemini_key else "local_tesseract_ocr" if local_ocr else "google_vision_configured" if google_credentials else "local_text_pdf_only"
    return {
        "status": "ok",
        "ocr": ocr_mode,
        "ai_scan": "configured" if gemini_key else "not_configured",
        "gemini": "configured" if gemini_key else "heuristic_parser",
        "local_ocr": "configured" if local_ocr else "missing_tesseract",
        "model": gemini_model_name() if gemini_key else None,
        "note": "AI scan is primary for photos and scanned PDFs when GEMINI_API_KEY/GOOGLE_API_KEY is configured. Local OCR is only a fallback.",
    }


@app.get("/api/usage")
def usage() -> dict[str, Any]:
    data = read_usage_log()
    today = usage_day()
    today_usage = usage_bucket(data, today)
    rpm_limit = int(os.getenv("GEMINI_REQUESTS_PER_MINUTE", "15"))
    recent_requests = len([request_time for request_time in gemini_requests if time.time() - request_time <= 60])
    return {
        "today": today,
        "usage": today_usage,
        "limits": {
            "local_gemini_rpm_limit": rpm_limit,
            "local_gemini_rpm_used": recent_requests,
            "max_upload_mb": 12,
            "portal_watch_seconds": 300,
        },
        "cloud": cloud_quota_status(),
        "links": {
            "ai_studio_rate_limits": "https://aistudio.google.com/app/rate-limit",
            "ai_studio_usage": "https://aistudio.google.com/app/usage",
            "ai_studio_spend": "https://aistudio.google.com/app/spend",
            "cloud_billing": "https://console.cloud.google.com/billing",
        },
        "recent_events": data.get("events", [])[-10:],
    }


@app.post("/api/settings/gemini")
def save_gemini_settings(payload: GeminiSettingsRequest) -> dict[str, Any]:
    api_key = payload.api_key.strip()
    if not api_key:
        raise HTTPException(status_code=400, detail="Paste a Gemini API key first.")
    if not (api_key.startswith("AIza") or len(api_key) >= 30):
        raise HTTPException(status_code=400, detail="This does not look like a valid Gemini API key.")
    model = (payload.model or gemini_model_name()).strip() or "gemini-2.5-flash"
    os.environ["GEMINI_API_KEY"] = api_key
    os.environ["GEMINI_MODEL"] = model
    save_backend_env({
        "GEMINI_API_KEY": api_key,
        "GEMINI_MODEL": model,
        "ALLOWED_ORIGINS": ",".join(allowed_origins),
        "GEMINI_REQUESTS_PER_MINUTE": os.getenv("GEMINI_REQUESTS_PER_MINUTE", "15"),
        "USE_MOCK_AI": os.getenv("USE_MOCK_AI", "false"),
    })
    return {"status": "saved", "ocr": "gemini_document_extraction", "model": model}


@app.post("/api/extract")
async def extract(file: UploadFile = File(...), form_type: str = Form(...)) -> dict[str, Any]:
    if form_type not in FORM_TITLES:
        raise HTTPException(status_code=400, detail="Unknown form type.")
    content_type = file.content_type or ""
    is_pdf = content_type == "application/pdf" or file.filename.lower().endswith(".pdf")
    is_image = content_type.startswith("image/")
    if not is_image and not is_pdf:
        raise HTTPException(status_code=400, detail="Please upload an image or PDF file.")

    file_bytes = await file.read()
    if len(file_bytes) > 12 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="File is too large. Please upload an image or PDF under 12 MB.")

    processing_type = "application/pdf" if is_pdf else content_type
    raw_text = extract_text_from_pdf(file_bytes) if is_pdf else ""
    if raw_text.strip():
        record_usage("local_text_pdf_scan", form_type=form_type)
        id_type = normalize_id_type(gemini_generate(DETECTION_PROMPT, raw_text))
        extraction_prompt = CITIZENSHIP_PROMPT if id_type == "CITIZENSHIP" else NID_PROMPT
        extracted = parse_json_response(gemini_generate(extraction_prompt, raw_text))
    elif gemini_api_key():
        record_usage("ocr_scan", form_type=form_type, provider="ai_gemini")
        extracted = extract_with_gemini_document(file_bytes, processing_type, file.filename)
        id_type = normalize_id_type(extracted.get("id_type") or "")
        raw_text = extracted.get("raw_text") or "Parsed directly from image/PDF with AI document extraction."
    elif local_ocr_available():
        record_usage("local_ocr_scan", form_type=form_type, provider="tesseract")
        raw_text = extract_text_with_local_ocr(file_bytes, processing_type, file.filename)
        if not raw_text.strip():
            raise HTTPException(status_code=422, detail="Local OCR found no readable text. Add an AI key for stronger photo extraction or try a clearer cropped image.")
        id_type = normalize_id_type(gemini_generate(DETECTION_PROMPT, raw_text))
        extraction_prompt = CITIZENSHIP_PROMPT if id_type == "CITIZENSHIP" else NID_PROMPT
        extracted = parse_json_response(gemini_generate(extraction_prompt, raw_text))
    elif google_vision_configured():
        record_usage("vision_scan", form_type=form_type)
        raw_text = extract_text_with_vision(file_bytes, processing_type)
        if not raw_text.strip():
            raise HTTPException(status_code=422, detail="No readable text was found in this file.")
        id_type = normalize_id_type(gemini_generate(DETECTION_PROMPT, raw_text))
        extraction_prompt = CITIZENSHIP_PROMPT if id_type == "CITIZENSHIP" else NID_PROMPT
        extracted = parse_json_response(gemini_generate(extraction_prompt, raw_text))
    else:
        raise HTTPException(status_code=500, detail="No OCR engine is ready. Install free Tesseract OCR, or add optional Gemini/Google Vision credentials.")
    master = unified_master(id_type, extracted)
    return {"id_type": id_type, "raw_text": raw_text, "master_data": master}


@app.post("/api/pdf")
def create_pdf(payload: PdfRequest) -> StreamingResponse:
    if payload.form_type not in FORM_TITLES:
        raise HTTPException(status_code=400, detail="Unknown form type.")
    record_usage("pdf_download", form_type=payload.form_type)
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, rightMargin=36, leftMargin=36, topMargin=36, bottomMargin=36)
    styles = getSampleStyleSheet()
    title_en, title_np = FORM_TITLES[payload.form_type]
    story = [
        Paragraph("Government of Nepal / नेपाल सरकार", styles["Title"]),
        Paragraph(f"{title_en} / {title_np}", styles["Heading2"]),
        Paragraph(f"Detected ID Type: {payload.id_type or 'Not specified'}", styles["Normal"]),
        Spacer(1, 16),
    ]
    rows = [["Field / क्षेत्र", "Value / विवरण"]]
    for key, value in payload.values.items():
        label = FIELD_LABELS.get(key, (key.replace("_", " ").title(), key))
        rows.append([f"{label[0]}\n{label[1]}", str(value or "")])
    table = Table(rows, colWidths=[190, 320])
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0B3D91")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#B8C2D8")),
        ("BACKGROUND", (0, 1), (-1, -1), colors.HexColor("#FBFCFF")),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 9),
        ("TOPPADDING", (0, 0), (-1, -1), 9),
    ]))
    story.append(table)
    story.extend([
        Spacer(1, 18),
        Paragraph("Applicant signature / आवेदकको हस्ताक्षर: ______________________________", styles["Normal"]),
        Spacer(1, 10),
        Paragraph("Office verification / कार्यालय प्रयोजन: ______________________________", styles["Normal"]),
    ])
    doc.build(story)
    buffer.seek(0)
    return StreamingResponse(
        buffer,
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename={payload.form_type}-filled-form.pdf"},
    )


@app.post("/api/portal/autofill")
def portal_autofill(payload: PortalAutofillRequest) -> dict[str, Any]:
    if not payload.portal_url.startswith(("http://", "https://")):
        raise HTTPException(status_code=400, detail="Enter a full portal URL starting with https:// or http://.")
    script_path = Path(__file__).resolve().parent.parent / "scripts" / "portal-fill.js"
    if not script_path.exists():
        raise HTTPException(status_code=500, detail="Portal automation script is missing.")
    command = ["node", str(script_path)]
    input_payload = json.dumps({
        "url": payload.portal_url,
        "values": payload.values,
        "wait_for_form": payload.wait_for_form,
        "wait_timeout_ms": payload.wait_timeout_ms,
        "browser_profile": payload.browser_profile,
    })
    try:
        process = subprocess.Popen(
            command,
            stdin=subprocess.PIPE,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            text=True,
            cwd=str(script_path.parent.parent),
            creationflags=getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0),
        )
        if process.stdin:
            process.stdin.write(input_payload)
            process.stdin.close()
    except FileNotFoundError as exc:
        raise HTTPException(status_code=500, detail="Node.js is required for browser portal autofill.") from exc
    record_usage("portal_session", portal_url=payload.portal_url)
    return {
        "status": "started",
        "filled_count": None,
        "message": "Your selected portal browser profile opened. Complete login, CAPTCHA, OTP, or location manually if needed. Autofill will watch for up to 5 minutes and fill safe visible fields across form pages as they appear. Review before submitting anything.",
    }


def mock_ocr_text() -> str:
    return """
    Government of Nepal Citizenship Certificate
    Name: Sita Shrestha
    नाम: सीता श्रेष्ठ
    Citizenship No: 27-01-78-12345
    Date of Birth: 2058-04-12
    Gender: Female
    Permanent Address: Kathmandu Metropolitan City Ward 12 Kathmandu
    Father's Name: Ram Shrestha
    Mother's Name: Maya Shrestha
    Grandfather's Name: Hari Shrestha
    Issued District: Kathmandu
    Issued Date: 2078-03-20
    Blood Group: B+
    """


def mock_citizenship_json() -> dict[str, Any]:
    return {
        "full_name_nepali": "सीता श्रेष्ठ",
        "full_name_english": "Sita Shrestha",
        "date_of_birth": "2058-04-12",
        "gender": "Female",
        "permanent_address": {"district": "Kathmandu", "municipality": "Kathmandu Metropolitan City", "ward": "12"},
        "citizenship_number": "27-01-78-12345",
        "issued_district": "Kathmandu",
        "issued_date": "2078-03-20",
        "expiry_date": None,
        "father_name": "Ram Shrestha",
        "mother_name": "Maya Shrestha",
        "grandfather_name": "Hari Shrestha",
        "spouse_name": None,
        "blood_group": "B+",
    }
