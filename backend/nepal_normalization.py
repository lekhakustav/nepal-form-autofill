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
    "id_type",
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


SAFE_FILL_CONFIDENCE_THRESHOLD = 0.8
FIELD_CONFIDENCE_THRESHOLDS = {
    "application_type": 0.75,
    "birth_place": 0.7,
    "blood_group": 0.88,
    "citizenship_issue_district": 0.8,
    "date_of_birth": 0.88,
    "email": 0.85,
    "father_name": 0.78,
    "full_name_english": 0.78,
    "full_name_nepali": 0.78,
    "gender": 0.9,
    "grandfather_name": 0.78,
    "issue_place": 0.7,
    "issued_date": 0.88,
    "issued_district": 0.8,
    "marital_status": 0.9,
    "mother_name": 0.78,
    "nationality": 0.9,
    "occupation": 0.7,
    "passport_type": 0.75,
    "phone": 0.85,
    "province": 0.8,
    "spouse_name": 0.78,
    "temporary_address_district": 0.8,
    "temporary_address_municipality": 0.7,
    "temporary_address_ward": 0.95,
    "address_district": 0.8,
    "address_municipality": 0.7,
    "address_ward": 0.95,
    "ward": 0.95,
    "expiry_date": 0.88,
}


def confidence_threshold_for_field(field: str) -> float:
    return FIELD_CONFIDENCE_THRESHOLDS.get(field, SAFE_FILL_CONFIDENCE_THRESHOLD)


def low_confidence_warning(field: str) -> str:
    return f"{field}_low_confidence"


def append_warning(warnings: list[str], warning: str) -> None:
    if warning and warning not in warnings:
        warnings.append(warning)


def gate_field_value(field: str, final: Any, meta: dict[str, Any], warnings: list[str]) -> tuple[Any, dict[str, Any]]:
    if isinstance(final, dict) or final in ("", None) or final == []:
        return final, meta
    if float(meta.get("confidence", 0.0)) < confidence_threshold_for_field(field):
        warning = low_confidence_warning(field)
        append_warning(warnings, warning)
        gated_meta = dict(meta)
        gated_meta["final"] = "" if isinstance(final, str) else None
        gated_meta["warnings"] = list(dict.fromkeys([*meta.get("warnings", []), warning]))
        return gated_meta["final"], gated_meta
    return final, meta


def get_raw_confidence(raw_extracted: dict[str, Any], field: str) -> float | None:
    confidences = raw_extracted.get("field_confidence") or {}
    if not isinstance(confidences, dict):
        return None
    direct = confidences.get(field)
    if direct is not None:
        try:
            return max(0.0, min(1.0, float(direct)))
        except (TypeError, ValueError):
            return None
    nested_map = {
        "permanent_address_district": ("permanent_address", "district"),
        "permanent_address_municipality": ("permanent_address", "municipality"),
        "permanent_address_ward": ("permanent_address", "ward"),
        "address_district": ("permanent_address", "district"),
        "address_municipality": ("permanent_address", "municipality"),
        "address_ward": ("permanent_address", "ward"),
        "temporary_address_district": ("temporary_address", "district"),
        "temporary_address_municipality": ("temporary_address", "municipality"),
        "temporary_address_ward": ("temporary_address", "ward"),
    }
    parent_key, child_key = nested_map.get(field, ("", ""))
    nested = confidences.get(parent_key) if parent_key else None
    if isinstance(nested, dict) and nested.get(child_key) is not None:
        try:
            return max(0.0, min(1.0, float(nested[child_key])))
        except (TypeError, ValueError):
            return None
    return None


def apply_raw_confidence(field: str, meta: dict[str, Any], raw_extracted: dict[str, Any]) -> dict[str, Any]:
    raw_confidence = get_raw_confidence(raw_extracted, field)
    if raw_confidence is None:
        return meta
    source = str(meta.get("source") or "")
    warnings = set(meta.get("warnings") or [])
    if source in {"fuzzy", "romanized", "inferred"} or warnings:
        combined = min(raw_confidence, float(meta.get("confidence", 0.0) or 0.0))
    else:
        combined = raw_confidence
    updated = dict(meta)
    updated["confidence"] = round(combined, 2)
    updated["extraction_confidence"] = raw_confidence
    return updated


def validate_address_hierarchy(
    profile: dict[str, Any],
    field_confidence: dict[str, float],
    debug_trace: dict[str, Any],
    warnings: list[str],
) -> None:
    permanent_address = profile.get("permanent_address") or {}
    if isinstance(permanent_address, dict):
        district = str(permanent_address.get("district") or "").strip()
        province = str(profile.get("province") or "").strip()
        expected_province = infer_province(district)
        if district and not province and expected_province:
            append_warning(warnings, "province_missing_for_permanent_address")
        if district and province and expected_province and read_text_key(province) != read_text_key(expected_province):
            warning = "province_conflicts_with_permanent_district"
            append_warning(warnings, warning)
            profile["province"] = ""
            field_confidence["province"] = min(float(field_confidence.get("province", 0.0) or 0.0), 0.4)
            if "province" in debug_trace:
                meta = dict(debug_trace["province"])
                meta["final"] = ""
                meta["warnings"] = list(dict.fromkeys([*meta.get("warnings", []), warning]))
                debug_trace["province"] = meta
    issued_district = str(profile.get("issued_district") or "").strip()
    citizenship_issue_district = str(profile.get("citizenship_issue_district") or "").strip()
    issue_place = str(profile.get("issue_place") or "").strip()
    if issued_district and citizenship_issue_district and read_text_key(issued_district) != read_text_key(citizenship_issue_district):
        append_warning(warnings, "citizenship_issue_district_conflicts_with_issued_district")
    if issue_place and issued_district and read_text_key(issue_place) == read_text_key(issued_district):
        append_warning(warnings, "issue_place_matches_issued_district")


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
    confidence = 0.96
    warnings: list[str] = []
    if has_devanagari(original):
        source = romanize_nepali(original)
        confidence = 0.84
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
    return title_case_words(working), 0.72 if source == "romanized" else 0.58, source, warnings


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
        fallback_confidence = 0.82 if field_key == "issue_place" and re.search(r"\b(office|department|administration|bureau|division)\b", read_text_key(canonical)) else 0.72 if field_key == "issue_place" else confidence
        return simplify_administrative_place_name(title_case_words(canonical)), fallback_confidence, source, warnings
    if field_key in {"address_ward", "permanent_address_ward", "temporary_address_ward"}:
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
        return title_case_words(text), 0.85, "literal", []
    if field == "occupation":
        return title_case_words(text), 0.78, "literal", []
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


def normalize_field(field: str, value: Any, raw_extracted: dict[str, Any] | None = None) -> tuple[Any, dict[str, Any]]:
    if value is None or value == "":
        return value, {
            "original": value,
            "final": value,
            "confidence": 0.0,
            "source": "empty",
            "warnings": [],
        }
    if isinstance(value, dict):
        return normalize_nested(field, value, raw_extracted)
    if field in {"citizenship_number", "nid_number", "old_passport_number", "phone", "email"}:
        text = str(value).strip()
        warnings: list[str] = []
        if field == "email":
            final = text.lower()
            confidence = 0.98 if re.search(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", final) else 0.72 if "@" in final else 0.4
            if confidence < 0.9:
                warnings.append("email_format_uncertain")
        elif field == "phone":
            final = re.sub(r"[^0-9+]", "", normalize_digits(text) if isinstance(text, str) else text)
            confidence = 0.98 if len(re.sub(r"\D", "", final)) >= 7 else 0.65
            if confidence < 0.9:
                warnings.append("phone_format_uncertain")
        else:
            final = normalize_digits(text)
            confidence = 0.98 if final else 0.0
        source = "literal"
        return final, {
            "original": value,
            "final": final,
            "confidence": round(confidence, 2),
            "source": source,
            "warnings": warnings,
        }
    if field in DATE_FIELDS:
        final, confidence, source, warnings = canonicalize_date(str(value))
    elif field in NAME_FIELDS:
        final, warnings, confidence, source = normalize_person_name(str(value))
    elif field in PLACE_FIELDS:
        final, confidence, source, warnings = canonicalize_place(field, str(value))
    elif field in SELECT_FIELDS:
        final, confidence, source, warnings = canonicalize_select(field, str(value))
    elif field == "occupation":
        final = title_case_words(str(value).strip())
        confidence = 0.78 if final else 0.0
        source = "literal"
        warnings = []
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


def normalize_nested(field: str, value: dict[str, Any], raw_extracted: dict[str, Any] | None = None) -> tuple[dict[str, Any], dict[str, Any]]:
    normalized: dict[str, Any] = {}
    trace = {"original": deepcopy(value), "final": {}, "confidence": 0.0, "source": "nested", "warnings": [], "children": {}}
    for nested_key, nested_value in value.items():
        nested_field = f"{field}_{nested_key}"
        final, meta = normalize_field(nested_field, nested_value, raw_extracted)
        meta = apply_raw_confidence(nested_field, meta, raw_extracted or {})
        final, meta = gate_field_value(nested_field, final, meta, trace["warnings"])
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
        if key == "id_type" or key == "raw_text" or key.startswith("field_") or key in {"validation_warnings", "unmatched_fields", "debug_trace"}:
            continue
        final, meta = normalize_field(key, value, raw_extracted)
        meta = apply_raw_confidence(key, meta, raw_extracted)
        final, meta = gate_field_value(key, final, meta, warnings)
        profile[key] = final
        field_confidence[key] = meta["confidence"]
        field_sources[key] = meta["source"]
        debug_trace[key] = meta
        warnings.extend(meta["warnings"])
    permanent_trace = debug_trace.get("permanent_address")
    if isinstance(permanent_trace, dict):
        for sub_key, flat_key in {
            "district": "address_district",
            "municipality": "address_municipality",
            "ward": "address_ward",
        }.items():
            if sub_key in permanent_trace.get("final", {}):
                meta = permanent_trace.get("children", {}).get(sub_key, {})
                meta = apply_raw_confidence(flat_key, meta, raw_extracted)
                final = permanent_trace["final"].get(sub_key)
                final, meta = gate_field_value(flat_key, final, meta, warnings)
                profile[flat_key] = final
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
                meta = temporary_trace.get("children", {}).get(sub_key, {})
                meta = apply_raw_confidence(flat_key, meta, raw_extracted)
                final = temporary_trace["final"].get(sub_key)
                final, meta = gate_field_value(flat_key, final, meta, warnings)
                profile[flat_key] = final
                field_confidence[flat_key] = float(meta.get("confidence", temporary_trace.get("confidence", 0.0)))
                field_sources[flat_key] = meta.get("source", temporary_trace.get("source", "nested"))
                debug_trace[flat_key] = {
                    "original": (temporary_trace.get("original") or {}).get(sub_key),
                    "final": profile[flat_key],
                    "confidence": field_confidence[flat_key],
                    "source": field_sources[flat_key],
                    "warnings": meta.get("warnings", []),
                }
    validate_address_hierarchy(profile, field_confidence, debug_trace, warnings)

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
