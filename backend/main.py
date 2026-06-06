import io
import json
import os
import re
import shutil
import subprocess
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

PASSPORT_PACKET_EXTRACTION_PROMPT = """Read all attached passport application source documents visually and return only one JSON object.
The files may include Nepali citizenship, NID, previous passport, supporting identity documents, or searchable PDF text.
Use exact visible values whenever possible. Combine data across all files.
Normalize dates exactly as visible when you cannot confidently convert between B.S. and A.D.
Focus on the values needed to autofill the Nepal ePassport online pre-enrollment form.
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
  "passport_type": string or null,
  "application_type": string or null,
  "birth_place": string or null,
  "old_passport_number": string or null,
  "phone": string or null,
  "email": string or null,
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
    return os.getenv("GEMINI_API_KEY")


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
        "GEMINI_MODEL",
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


def gemini_model_name() -> str:
    return os.getenv("GEMINI_MODEL", "gemini-3.5-flash")


def extract_with_gemini_passport_packet(uploaded_files: list[dict[str, Any]]) -> dict[str, Any]:
    if demo_data_enabled():
        return {
            **mock_citizenship_json(),
            "id_type": "CITIZENSHIP",
            "passport_type": "Ordinary 34 pages",
            "application_type": "New",
            "birth_place": "Kathmandu",
            "phone": "9800000000",
            "email": "sita@example.com",
            "raw_text": mock_ocr_text(),
        }
    if genai is None:
        raise HTTPException(status_code=500, detail="Gemini SDK is not installed.")
    api_key = gemini_api_key()
    if not api_key:
        raise HTTPException(status_code=500, detail="Add GEMINI_API_KEY to backend/.env to extract passport details from photos and PDFs.")

    enforce_gemini_rate_limit()
    try:
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel(gemini_model_name())
        parts: list[Any] = [PASSPORT_PACKET_EXTRACTION_PROMPT]
        for index, uploaded in enumerate(uploaded_files, start=1):
            filename = uploaded["filename"]
            content_type = uploaded["content_type"]
            file_bytes = uploaded["bytes"]
            embedded_text = extract_text_from_pdf(file_bytes) if content_type == "application/pdf" else ""
            if embedded_text:
                parts.append(f"\n\nSEARCHABLE PDF TEXT FROM FILE {index} ({filename}):\n{embedded_text[:12000]}")
            for part in ai_document_parts(file_bytes, content_type):
                parts.append(part)
        response = model.generate_content(
            parts,
            generation_config={"temperature": 0, "response_mime_type": "application/json"},
        )
        record_usage(
            "gemini_call",
            model=gemini_model_name(),
            source="passport_packet_extraction",
            file_count=len(uploaded_files),
            **response_usage_metadata(response),
        )
        extracted = parse_json_response(response.text or "")
        extracted["id_type"] = normalize_id_type(extracted.get("id_type") or heuristic_detect_id_type(extracted.get("raw_text") or ""))
        return extracted
    except HTTPException:
        raise
    except Exception as exc:
        message = str(exc).lower()
        if "quota" in message or "resource_exhausted" in message or "429" in message:
            raise HTTPException(status_code=429, detail="Gemini rate limit reached. Please wait and try again.") from exc
        raise HTTPException(status_code=502, detail=f"Gemini passport extraction failed: {exc}") from exc


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
        "passport_type": data.get("passport_type"),
        "application_type": data.get("application_type"),
        "birth_place": data.get("birth_place"),
        "old_passport_number": data.get("old_passport_number"),
        "phone": data.get("phone"),
        "email": data.get("email"),
    })


@app.get("/api/health")
def health() -> dict[str, Any]:
    gemini_key = bool(gemini_api_key())
    return {
        "status": "ok",
        "ocr": "gemini_passport_extraction" if gemini_key else "gemini_key_required",
        "ai_scan": "configured" if gemini_key else "not_configured",
        "gemini": "configured" if gemini_key else "missing_api_key",
        "model": gemini_model_name() if gemini_key else None,
        "note": "Passport photo/PDF extraction uses Gemini locally through this backend. Add GEMINI_API_KEY to backend/.env before scanning real documents.",
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
    model = (payload.model or gemini_model_name()).strip() or "gemini-3.5-flash"
    os.environ["GEMINI_API_KEY"] = api_key
    os.environ["GEMINI_MODEL"] = model
    save_backend_env({
        "GEMINI_API_KEY": api_key,
        "GEMINI_MODEL": model,
        "ALLOWED_ORIGINS": ",".join(allowed_origins),
        "GEMINI_REQUESTS_PER_MINUTE": os.getenv("GEMINI_REQUESTS_PER_MINUTE", "15"),
        "USE_MOCK_AI": os.getenv("USE_MOCK_AI", "false"),
    })
    return {"status": "saved", "ocr": "gemini_passport_extraction", "model": model}


@app.post("/api/extract")
async def extract(files: list[UploadFile] = File(...), form_type: str = Form(...)) -> dict[str, Any]:
    if form_type != "passport":
        raise HTTPException(status_code=400, detail="Passport is the only supported form in this local autofill build.")
    if not files:
        raise HTTPException(status_code=400, detail="Upload at least one passport source photo or PDF.")
    if not gemini_api_key() and not demo_data_enabled():
        raise HTTPException(status_code=500, detail="Add GEMINI_API_KEY to backend/.env before extracting passport details from photos or PDFs.")

    uploaded_files: list[dict[str, Any]] = []
    total_bytes = 0
    for upload in files:
        filename = upload.filename or "uploaded-document"
        content_type = upload.content_type or ""
        is_pdf = content_type == "application/pdf" or filename.lower().endswith(".pdf")
        is_image = content_type.startswith("image/")
        if not is_image and not is_pdf:
            raise HTTPException(status_code=400, detail=f"{filename} is not an image or PDF file.")
        file_bytes = await upload.read()
        if len(file_bytes) > 12 * 1024 * 1024:
            raise HTTPException(status_code=413, detail=f"{filename} is too large. Upload each image or PDF under 12 MB.")
        total_bytes += len(file_bytes)
        if total_bytes > 32 * 1024 * 1024:
            raise HTTPException(status_code=413, detail="The passport document packet is too large. Keep the combined upload under 32 MB.")
        uploaded_files.append({
            "filename": filename,
            "content_type": "application/pdf" if is_pdf else content_type,
            "bytes": file_bytes,
        })

    record_usage("ocr_scan", form_type=form_type, provider="gemini_passport_packet", file_count=len(uploaded_files))
    extracted = extract_with_gemini_passport_packet(uploaded_files)
    id_type = normalize_id_type(extracted.get("id_type") or "")
    raw_text = extracted.get("raw_text") or "Parsed from uploaded passport source files with Gemini."
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
