from __future__ import annotations

import difflib
import json
import re
from copy import deepcopy
from pathlib import Path
from typing import Any

from indic_transliteration import sanscript
from indic_transliteration.sanscript import transliterate

DATA_PATH = Path(__file__).resolve().parent.parent / "data" / "nepal_places.json"

try:
    PLACE_DATA = json.loads(DATA_PATH.read_text(encoding="utf-8"))
except Exception:  # pragma: no cover
    PLACE_DATA = {
        "district_to_province": {},
        "province_aliases": {},
        "country_aliases": {},
        "common_place_aliases": {},
        "person_name_corrections": {},
    }

DISTRICT_TO_PROVINCE: dict[str, str] = PLACE_DATA.get("district_to_province", {})
PROVINCE_ALIASES: dict[str, list[str]] = PLACE_DATA.get("province_aliases", {})
COUNTRY_ALIASES: dict[str, list[str]] = PLACE_DATA.get("country_aliases", {})
COMMON_PLACE_ALIASES: dict[str, list[str]] = PLACE_DATA.get("common_place_aliases", {})
PERSON_NAME_CORRECTIONS: dict[str, str] = PLACE_DATA.get("person_name_corrections", {})

NAME_FIELDS = {
    "full_name_english",
    "full_name_nepali",
    "father_name",
    "mother_name",
    "grandfather_name",
    "spouse_name",
    "guardian_name",
}

PLACE_FIELDS = {
    "address_district",
    "address_municipality",
    "address_ward",
    "birth_place",
    "citizenship_issue_district",
    "issue_place",
    "issued_district",
    "permanent_address_district",
    "permanent_address_municipality",
    "permanent_address_ward",
    "province",
    "registration_place",
    "polling_place",
    "temporary_address_district",
    "temporary_address_municipality",
    "temporary_address_ward",
    "training_center",
    "exam_center",
    "bank_branch",
    "voter_area",
}

SELECT_FIELDS = {
    "application_type",
    "blood_group",
    "gender",
    "marital_status",
    "nationality",
    "passport_type",
    "province",
    "country",
    "account_type",
    "license_category",
    "vehicle_type",
    "level",
    "service_group",
}

DATE_FIELDS = {
    "date_of_birth",
    "date_of_birth_ad",
    "date_of_birth_bs",
    "issued_date",
    "issued_date_ad",
    "issued_date_bs",
    "expiry_date",
    "expiry_date_ad",
    "expiry_date_bs",
}

KNOWN_FIELDS = {
    "full_name_english",
    "full_name_nepali",
    "date_of_birth",
    "date_of_birth_ad",
    "date_of_birth_bs",
    "gender",
    "nationality",
    "marital_status",
    "province",
    "permanent_address",
    "temporary_address",
    "address_district",
    "address_municipality",
    "address_ward",
    "temporary_address_district",
    "temporary_address_municipality",
    "temporary_address_ward",
    "citizenship_number",
    "nid_number",
    "issued_district",
    "citizenship_issue_district",
    "issue_place",
    "issued_date",
    "issued_date_ad",
    "issued_date_bs",
    "expiry_date",
    "expiry_date_ad",
    "expiry_date_bs",
    "father_name",
    "mother_name",
    "grandfather_name",
    "spouse_name",
    "blood_group",
    "passport_type",
    "application_type",
    "birth_place",
    "old_passport_number",
    "phone",
    "email",
    "occupation",
    "raw_text",
    "field_confidence",
    "field_sources",
    "validation_warnings",
    "unmatched_fields",
    "debug_trace",
    "province_guess",
}


def read_text_key(value: Any) -> str:
    text = str(value or "")
    text = text.lower().strip()
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def has_devanagari(value: Any) -> bool:
    return bool(re.search(r"[\u0900-\u097f]", str(value or "")))


def normalize_digits(value: Any) -> Any:
    if isinstance(value, str):
        return value.translate(str.maketrans({
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
        }))
    if isinstance(value, dict):
        return {key: normalize_digits(item) for key, item in value.items()}
    if isinstance(value, list):
        return [normalize_digits(item) for item in value]
    return value


def romanize_nepali(value: str) -> str:
    if not value:
        return ""
    try:
        return transliterate(value, sanscript.DEVANAGARI, sanscript.ITRANS)
    except Exception:
        return value


def simplify_administrative_place_name(value: str) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    simplified = re.sub(
        r"\s+(Metropolitan City|Sub-Metropolitan City|Municipality|Rural Municipality|Mahanagarpalika|Upamahanagarpalika|Nagarpalika)$",
        "",
        text,
        flags=re.IGNORECASE,
    ).strip()
    return simplified or text


def title_case_words(value: str) -> str:
    if not value:
        return ""
    tokens = re.split(r"(\s+|-)", value.strip())
    keep = {"KC", "NID", "DOB", "BS", "AD", "ID"}
    output: list[str] = []
    for token in tokens:
        if not token or token.isspace() or token == "-":
            output.append(token)
            continue
        upper = token.upper().replace(".", "")
        if upper in keep:
            output.append(upper)
            continue
        if token.isupper() and len(token) <= 3:
            output.append(token)
            continue
        output.append(token[:1].upper() + token[1:].lower())
    return "".join(output)


def compact(value: str) -> str:
    return re.sub(r"\s+", "", read_text_key(value))


def best_similarity(value: str, candidates: list[str]) -> tuple[str | None, float]:
    normalized = read_text_key(value)
    compacted = compact(value)
    best: tuple[str | None, float] = (None, 0.0)
    for candidate in candidates:
      candidate_norm = read_text_key(candidate)
      candidate_compact = compact(candidate)
      score = max(
          difflib.SequenceMatcher(None, normalized, candidate_norm).ratio(),
          difflib.SequenceMatcher(None, compacted, candidate_compact).ratio(),
      )
      if normalized == candidate_norm or compacted == candidate_compact:
        score = 1.0
      if score > best[1]:
        best = (candidate, score)
    return best


def alias_candidates(table: dict[str, list[str]]) -> dict[str, list[str]]:
    candidates: dict[str, list[str]] = {}
    for canonical, aliases in table.items():
        values = {canonical}
        values.update(aliases or [])
        values.add(read_text_key(canonical))
        values.add(compact(canonical))
        candidates[canonical] = sorted({v for v in values if v})
    return candidates


PROVINCE_CANDIDATES = alias_candidates(PROVINCE_ALIASES)
COUNTRY_CANDIDATES = alias_candidates(COUNTRY_ALIASES)
PLACE_CANDIDATES = alias_candidates(COMMON_PLACE_ALIASES)
DISTRICT_CANDIDATES = {
    canonical: sorted({
        canonical,
        read_text_key(canonical),
        compact(canonical),
        canonical.replace(" ", ""),
    })
    for canonical in DISTRICT_TO_PROVINCE
}


def normalize_person_name(value: str) -> tuple[str, list[str], float, str]:
    original = str(value or "").strip()
    if not original:
        return "", [], 0.0, "empty"
    source = original
    confidence = 0.6
    warnings: list[str] = []
    if has_devanagari(original):
        source = romanize_nepali(original)
        confidence = 0.72
        warnings.append("romanized_from_devanagari")
    source = source.replace(".", " ").replace("_", " ")
    source = re.sub(r"\s+", " ", source).strip()
    tokens = []
    for token in source.split():
        normalized = read_text_key(token)
        correction = None
        if normalized in PERSON_NAME_CORRECTIONS:
            correction = PERSON_NAME_CORRECTIONS[normalized]
        else:
            matched, score = best_similarity(token, list(PERSON_NAME_CORRECTIONS.keys()))
            if matched and score >= 0.88:
                correction = PERSON_NAME_CORRECTIONS[matched]
        cleaned = correction or token
        tokens.append(title_case_words(cleaned))
    result = " ".join(tokens)
    if has_devanagari(result):
        warnings.append("non_latin_output")
        confidence = min(confidence, 0.35)
    if re.search(r"(.)\1{2,}", result.lower()):
        warnings.append("suspicious_repetition")
        confidence = min(confidence, 0.55)
    return result, warnings, round(confidence, 2), "romanized" if has_devanagari(original) else "latin"


def canonicalize_from_tables(value: str, candidates: dict[str, list[str]]) -> tuple[str, float, str, list[str]]:
    original = str(value or "").strip()
    if not original:
        return "", 0.0, "empty", []
    warnings: list[str] = []
    source = "latin"
    working = original
    if has_devanagari(working):
        working = romanize_nepali(working)
        source = "romanized"
        warnings.append("romanized_from_devanagari")
    working = working.replace(".", " ")
    working = re.sub(r"\s+", " ", working).strip()
    normalized = read_text_key(working)
    compacted = compact(working)
    for canonical, aliases in candidates.items():
        for alias in aliases:
            if normalized == read_text_key(alias) or compacted == compact(alias):
                return canonical, 0.98 if source == "latin" else 0.94, source, warnings
    best_name = None
    best_score = 0.0
    for canonical, aliases in candidates.items():
        pool = [canonical, *aliases]
        candidate, score = best_similarity(working, pool)
        if candidate and score > best_score:
            best_name = canonical
            best_score = score
    if best_name and best_score >= 0.72:
        warnings.append("fuzzy_match")
        return best_name, round(0.65 + best_score * 0.3, 2), "fuzzy", warnings
    return title_case_words(working), 0.48 if source == "romanized" else 0.55, source, warnings


def canonicalize_place(field: str, value: str) -> tuple[str, float, str, list[str]]:
    field_key = field.lower()
    if not value:
        return "", 0.0, "empty", []
    if field_key == "province":
        return canonicalize_from_tables(value, PROVINCE_CANDIDATES)
    if field_key in {"country", "nationality"}:
        canonical, confidence, source, warnings = canonicalize_from_tables(value, COUNTRY_CANDIDATES)
        if canonical.lower() == "nepal":
            canonical = "Nepal"
        if field_key == "nationality" and read_text_key(canonical) in {"nepal", "nepali"}:
            canonical = "Nepali"
        return canonical, confidence, source, warnings
    if field_key in {"address_district", "issued_district", "citizenship_issue_district", "permanent_address_district", "temporary_address_district"}:
        canonical, confidence, source, warnings = canonicalize_from_tables(value, DISTRICT_CANDIDATES)
        if canonical in DISTRICT_TO_PROVINCE:
            return canonical, confidence, source, warnings
        return canonical, confidence, source, warnings
    if field_key in {"birth_place", "issue_place", "registration_place", "polling_place", "bank_branch", "training_center", "exam_center", "address_municipality", "permanent_address_municipality", "temporary_address_municipality", "voter_area"}:
        canonical, confidence, source, warnings = canonicalize_from_tables(value, PLACE_CANDIDATES)
        if canonical in PLACE_CANDIDATES:
            return simplify_administrative_place_name(canonical), confidence, source, warnings
        if has_devanagari(value):
            warnings.append("romanized_place")
        return simplify_administrative_place_name(title_case_words(canonical)), confidence, source, warnings
    if field_key in {"address_ward", "temporary_address_ward"}:
        digits = re.sub(r"[^0-9]", "", normalize_digits(value) if isinstance(value, str) else str(value))
        return digits or str(value).strip(), 0.99 if digits else 0.45, "numeric", []
    return title_case_words(str(value).strip()), 0.55, "literal", []


def canonicalize_select(field: str, value: str) -> tuple[str, float, str, list[str]]:
    text = str(value or "").strip()
    if not text:
        return "", 0.0, "empty", []
    lowered = read_text_key(text)
    if field == "gender":
        if lowered in {"m", "male", "purush", "man", "linga male"}:
            return "Male", 0.99, "synonym", []
        if lowered in {"f", "female", "mahila"}:
            return "Female", 0.99, "synonym", []
        if lowered in {"other", "others", "anya"}:
            return "Other", 0.95, "synonym", []
    if field == "marital_status":
        for canonical, aliases in {
            "Married": ["married", "vivahit", "wedded"],
            "Unmarried": ["unmarried", "single", "avivahit", "not married"],
            "Divorced": ["divorced", "separated", "gharsandhan"],
            "Widowed": ["widowed", "widower", "widow", "vidhwa", "widowed woman", "widowed man"]
        }.items():
            if lowered == read_text_key(canonical) or lowered in {read_text_key(alias) for alias in aliases}:
                return canonical, 0.98, "synonym", []
    if field == "nationality":
        if lowered in {"nepali", "nepalese", "citizen of nepal"}:
            return "Nepali", 0.99, "synonym", []
        if lowered in {"nepal", "nepal citizen"}:
            return "Nepali", 0.93, "synonym", []
    if field == "country":
        if lowered in {"nepal", "nepali"}:
            return "Nepal", 0.99, "synonym", []
    if field == "province":
        return canonicalize_place(field, text)
    if field in {"application_type", "passport_type", "blood_group", "account_type", "license_category", "vehicle_type", "level", "service_group"}:
        return title_case_words(text), 0.7, "literal", []
    return title_case_words(text), 0.65, "literal", []


def canonicalize_date(value: str) -> tuple[str, float, str, list[str]]:
    text = str(value or "").strip()
    if not text:
        return "", 0.0, "empty", []
    normalized = normalize_digits(text)
    normalized = normalized.replace("/", "-").replace(".", "-")
    match = re.search(r"\b(\d{4})-(\d{1,2})-(\d{1,2})\b", normalized)
    if match:
        year, month, day = match.groups()
        return f"{year}-{int(month):02d}-{int(day):02d}", 0.98, "iso", []
    match = re.search(r"\b(\d{1,2})-(\d{1,2})-(\d{4})\b", normalized)
    if match:
        day, month, year = match.groups()
        return f"{year}-{int(month):02d}-{int(day):02d}", 0.9, "reordered", ["date_reordered"]
    return normalized, 0.58, "literal", ["unparsed_date"]


def infer_province(district: str | None) -> str | None:
    if not district:
        return None
    return DISTRICT_TO_PROVINCE.get(district)


def normalize_field(field: str, value: Any) -> tuple[Any, dict[str, Any]]:
    if value is None or value == "":
        return value, {
            "original": value,
            "final": value,
            "confidence": 0.0,
            "source": "empty",
            "warnings": [],
        }
    if isinstance(value, dict):
        return normalize_nested(field, value)
    if field in DATE_FIELDS:
        final, confidence, source, warnings = canonicalize_date(str(value))
    elif field in NAME_FIELDS:
        final, warnings, confidence, source = normalize_person_name(str(value))
    elif field in PLACE_FIELDS:
        final, confidence, source, warnings = canonicalize_place(field, str(value))
    elif field in SELECT_FIELDS:
        final, confidence, source, warnings = canonicalize_select(field, str(value))
    else:
        final = title_case_words(str(value).strip())
        confidence = 0.65 if final else 0.0
        source = "literal"
        warnings = []
    return final, {
        "original": value,
        "final": final,
        "confidence": round(confidence, 2),
        "source": source,
        "warnings": warnings,
    }


def normalize_nested(field: str, value: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    normalized: dict[str, Any] = {}
    trace = {"original": deepcopy(value), "final": {}, "confidence": 0.0, "source": "nested", "warnings": [], "children": {}}
    for nested_key, nested_value in value.items():
        nested_field = f"{field}_{nested_key}"
        final, meta = normalize_field(nested_field, nested_value)
        normalized[nested_key] = final
        trace["final"][nested_key] = final
        trace["children"][nested_key] = meta
        trace["confidence"] = max(trace["confidence"], meta["confidence"])
        trace["warnings"].extend(meta["warnings"])
    return normalized, trace


def normalize_profile(master: dict[str, Any], raw_extracted: dict[str, Any] | None = None, id_type: str | None = None) -> dict[str, Any]:
    profile = deepcopy(master)
    raw_extracted = raw_extracted or {}
    field_confidence: dict[str, float] = {}
    field_sources: dict[str, str] = {}
    debug_trace: dict[str, Any] = {}
    warnings: list[str] = []

    for key, value in list(profile.items()):
        if key.startswith("field_") or key in {"validation_warnings", "unmatched_fields", "debug_trace"}:
            continue
        final, meta = normalize_field(key, value)
        profile[key] = final
        field_confidence[key] = meta["confidence"]
        field_sources[key] = meta["source"]
        debug_trace[key] = meta
        warnings.extend(meta["warnings"])

    permanent_address = profile.get("permanent_address") or {}
    if isinstance(permanent_address, dict):
        district = permanent_address.get("district")
        province = profile.get("province") or infer_province(district)
        if province:
            profile["province"] = province
            field_confidence["province"] = 0.9 if profile.get("province") else 0.72
            field_sources["province"] = "inferred"
            debug_trace["province"] = {
                "original": profile.get("province"),
                "final": province,
                "confidence": field_confidence["province"],
                "source": "inferred",
                "warnings": [] if profile.get("province") else ["province_inferred_from_district"],
            }
    permanent_trace = debug_trace.get("permanent_address")
    if isinstance(permanent_trace, dict):
        for sub_key, flat_key in {
            "district": "address_district",
            "municipality": "address_municipality",
            "ward": "address_ward",
        }.items():
            if sub_key in permanent_trace.get("final", {}):
                profile[flat_key] = permanent_trace["final"].get(sub_key)
                meta = permanent_trace.get("children", {}).get(sub_key, {})
                field_confidence[flat_key] = float(meta.get("confidence", permanent_trace.get("confidence", 0.0)))
                field_sources[flat_key] = meta.get("source", permanent_trace.get("source", "nested"))
                debug_trace[flat_key] = {
                    "original": (permanent_trace.get("original") or {}).get(sub_key),
                    "final": profile[flat_key],
                    "confidence": field_confidence[flat_key],
                    "source": field_sources[flat_key],
                    "warnings": meta.get("warnings", []),
                }
    temporary_trace = debug_trace.get("temporary_address")
    if isinstance(temporary_trace, dict):
        for sub_key, flat_key in {
            "district": "temporary_address_district",
            "municipality": "temporary_address_municipality",
            "ward": "temporary_address_ward",
        }.items():
            if sub_key in temporary_trace.get("final", {}):
                profile[flat_key] = temporary_trace["final"].get(sub_key)
                meta = temporary_trace.get("children", {}).get(sub_key, {})
                field_confidence[flat_key] = float(meta.get("confidence", temporary_trace.get("confidence", 0.0)))
                field_sources[flat_key] = meta.get("source", temporary_trace.get("source", "nested"))
                debug_trace[flat_key] = {
                    "original": (temporary_trace.get("original") or {}).get(sub_key),
                    "final": profile[flat_key],
                    "confidence": field_confidence[flat_key],
                    "source": field_sources[flat_key],
                    "warnings": meta.get("warnings", []),
                }
    if not profile.get("nationality") and id_type in {"CITIZENSHIP", "NID"}:
        profile["nationality"] = "Nepali"
        field_confidence["nationality"] = 0.93
        field_sources["nationality"] = "inferred"
        debug_trace["nationality"] = {
            "original": None,
            "final": "Nepali",
            "confidence": 0.93,
            "source": "inferred",
            "warnings": ["nationality_inferred_from_id_type"],
        }
    if not profile.get("issue_place") and profile.get("issued_district"):
        profile["issue_place"] = profile["issued_district"]
        field_confidence["issue_place"] = 0.82
        field_sources["issue_place"] = "inferred"
        debug_trace["issue_place"] = {
            "original": None,
            "final": profile["issue_place"],
            "confidence": 0.82,
            "source": "inferred",
            "warnings": ["issue_place_inferred_from_issued_district"],
        }
    if not profile.get("citizenship_issue_district") and profile.get("issued_district"):
        profile["citizenship_issue_district"] = profile["issued_district"]
        field_confidence["citizenship_issue_district"] = 0.8
        field_sources["citizenship_issue_district"] = "inferred"
        debug_trace["citizenship_issue_district"] = {
            "original": None,
            "final": profile["citizenship_issue_district"],
            "confidence": 0.8,
            "source": "inferred",
            "warnings": ["citizenship_issue_district_inferred"],
        }

    normalized_raw_keys = set(KNOWN_FIELDS)
    unmatched_fields = [
        key
        for key in raw_extracted.keys()
        if key not in normalized_raw_keys and key not in {"permanent_address", "temporary_address", "field_confidence", "field_sources", "validation_warnings", "unmatched_fields", "debug_trace"}
    ]
    profile["field_confidence"] = field_confidence
    profile["field_sources"] = field_sources
    profile["validation_warnings"] = sorted({warning for warning in warnings if warning})
    profile["unmatched_fields"] = sorted({field for field in unmatched_fields if field})
    profile["debug_trace"] = debug_trace
    profile["raw_text"] = raw_extracted.get("raw_text") or profile.get("raw_text") or ""
    if "temporary_address" not in profile:
        profile["temporary_address"] = raw_extracted.get("temporary_address") or {"district": "", "municipality": "", "ward": ""}
    return normalize_digits(profile)
