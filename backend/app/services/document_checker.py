"""Deterministic application document checks over structured evidence."""

from datetime import date, timedelta
from decimal import Decimal, InvalidOperation
from difflib import SequenceMatcher
import os
import re
from unicodedata import category, normalize

from text_unidecode import unidecode

from ..models.domain import RuleStatus, age_on_date
from ..schemas.document_checks import DocumentEvidence, EvidenceField
from .document_language import CANONICAL, ascii_digits, detected_language
from .eligibility_engine import evaluate_scheme

# Checklist versions are independent of rule versions and tied to catalogue snapshots.
CHECKLISTS = {
    ("pb_old_age_pension", "2026-09-22"): ("identity", "residence", "age", "bank"),
    ("HR-OASA-002", "2026-09-22"): ("family_id", "age", "bank"),
}
PROFILE_PATHS = {
    "name": ("personal", "name"),
    "date_of_birth": ("personal", "date_of_birth"),
    "state": ("location", "state"),
    "district": ("location", "district"),
    "pin": ("location", "pin"),
    "annual_household_income": ("household", "household_annual_income"),
    "social_category": ("social", "social_category"),
    "disability_percentage": ("personal", "disability_percentage"),
}
RULE_FIELDS = {
    "age": "date_of_birth",
    "location.state": "state",
    "household.household_annual_income": "annual_household_income",
}
RULE_DOCUMENT_TYPES = {
    "date_of_birth": {"identity", "age", "family_id"},
    "state": {"residence", "family_id"},
    "annual_household_income": {"income"},
}
HONORIFICS = {"mr", "mrs", "ms", "dr", "shri", "smt", "kumari", "sri"}
NAME_FIELDS = {"name", "father_name", "mother_name"}
ADDRESS_COMPARISON_FIELDS = {"address", "house_number", "street", "sector", "village", "city", "state", "district", "pin"}
EXTRA_FIELDS = NAME_FIELDS | ADDRESS_COMPARISON_FIELDS | {"gender", "place_of_birth"}
ADDRESS_ABBREVIATIONS = {"rd": "road", "sec": "sector", "dist": "district", "vill": "village"}


def confidence_threshold(name, fallback):
    try:
        value = float(os.getenv(name, str(fallback)))
        return value if 0 <= value <= 1 else fallback
    except ValueError:
        return fallback


def normalized_value(field, value):
    if value is None:
        return None
    text = ascii_digits(str(value).strip())
    if text.casefold() in {"", "unknown", "prefer_not_to_say", "n/a"}:
        return None
    if field in {"annual_household_income", "disability_percentage"}:
        try:
            amount = Decimal(text.replace(",", ""))
            return amount if amount.is_finite() and 0 <= amount <= (100 if field == "disability_percentage" else 10**15) else None
        except InvalidOperation:
            return None
    if field in {"date_of_birth", "expires_on"}:
        try:
            return date.fromisoformat(text)
        except ValueError:
            return None
    if field == "pin":
        return text if re.fullmatch(r"[1-9][0-9]{5}", text) else None
    canonical = normalize("NFKC", text).casefold()
    if field in {"address", "house_number", "street", "sector"}:
        words = "".join(char if category(char)[0] in {"L", "M", "N"} else " " for char in canonical).split()
        if field in {"address", "street"}:
            words = [ADDRESS_ABBREVIATIONS.get(word, word) for word in words]
        return " ".join(words) or None
    words = "".join(char if category(char)[0] in {"L", "M"} else " " for char in canonical).split()
    if not words or any(char.isdigit() for char in text):
        return None
    if field in NAME_FIELDS:
        words = sorted(word for word in words if word not in HONORIFICS)
    joined = " ".join(words)
    return CANONICAL.get(field, {}).get(joined, joined) or None


def name_similarity(left, right):
    if left == right:
        return "exact_match"
    left_words, right_words = left.split(), right.split()
    if set(left_words) & set(right_words):
        for short, long in ((left_words, right_words), (right_words, left_words)):
            if len(short) <= len(long) and all(
                any(word == other or (len(word) == 1 and other.startswith(word)) for other in long)
                for word in short
            ):
                return "likely_match"
    similarity = SequenceMatcher(None, left, right).ratio()
    if not (left.isascii() and right.isascii()):
        left_roman = " ".join(sorted(unidecode(left).casefold().split()))
        right_roman = " ".join(sorted(unidecode(right).casefold().split()))
        if left_roman and right_roman and SequenceMatcher(None, left_roman, right_roman).ratio() >= 0.73:
            return "likely_match"
    return "possible_mismatch" if similarity >= 0.72 else "clear_mismatch"


def evidence_at(index: int, field: str, evidence: EvidenceField):
    score = evidence.ocr_confidence
    low = confidence_threshold("DOCUMENT_OCR_LOW_THRESHOLD", 0.70)
    high = max(low, confidence_threshold("DOCUMENT_OCR_HIGH_THRESHOLD", 0.90))
    return {
        "document": index,
        "field": field,
        "language": detected_language(evidence.original_value or evidence.value),
        "user_confirmed": evidence.user_confirmed,
        "date_format_uncertain": evidence.date_format_uncertain,
        "confidence_band": None if score is None else "low" if score < low else "medium" if score < high else "high",
        "page": evidence.page,
        "bounding_box": evidence.bounding_box,
        "ocr_confidence": evidence.ocr_confidence,
        "extraction_confidence": evidence.extraction_confidence,
    }


def check_documents(scheme, documents: list[DocumentEvidence], profile: dict, today: date, *, compare_unconfirmed: bool = False):
    checklist = CHECKLISTS[(scheme.scheme_id, str(scheme.last_checked))] if scheme else ()
    findings = []
    comparisons = []
    usable_types = set()
    seen_types = set()
    entries = {key: [] for key in sorted(PROFILE_PATHS.keys() | EXTRA_FIELDS)}
    conflicts = set()
    checked_fields = 0
    compared_fields = set()

    def issue(severity, code, message, action, *, document=None, evidence=(), source_url=None):
        findings.append({
            "severity": severity, "code": code, "message": message, "action": action,
            "document": document, "evidence": list(evidence), "source_url": source_url,
        })

    for index, document in enumerate(documents, start=1):
        kind = document.document_type
        seen_types.add(kind)
        severity = "blocker" if kind in checklist else "warning"
        if kind == "unknown":
            issue("warning", "unknown_type", "Document type could not be determined.",
                  "Select the correct evidence type or replace the document.", document=index)
        if not document.readable or document.missing_pages:
            issue(severity, "incomplete_document", "The document is unreadable or has missing pages.",
                  "Prepare a readable copy with all pages.", document=index)
        expired = document.expires_on is not None and document.expires_on < today
        if expired:
            issue(severity, "expired_document", "The document has expired.",
                  "Prepare a current copy.", document=index)
        elif document.expires_on is not None and document.expires_on <= today + timedelta(days=30):
            issue("information", "expiring_document", "The document expires within 30 days.",
                  "Check that it will still be valid on the submission date.", document=index)
        if kind == "unknown" or expired or not document.readable or document.missing_pages:
            continue
        usable_types.add(kind)
        if not document.fields:
            issue("warning", "no_fields", "No fields were entered for comparison.",
                  "Enter the relevant details and their page numbers.", document=index)
        for field, evidence in document.fields.items():
            location = evidence_at(index, field, evidence)
            checked_fields += 1
            value = normalized_value(field, evidence.value)
            if value is None or (field == "date_of_birth" and value > today):
                issue("warning", "unreadable_field", "This field could not be interpreted.",
                      "Check the original and enter the correct value.", evidence=[location])
                continue
            confidences = (evidence.ocr_confidence, evidence.extraction_confidence)
            scores = [score for score in confidences if score is not None]
            if not evidence.user_confirmed and scores and (len(scores) < 2 or min(scores) < 0.85):
                issue("warning", "confirm_field", "This extracted field needs confirmation.",
                      "Read the original and enter a confirmed value.", evidence=[location])
                if not compare_unconfirmed or scheme is not None:
                    continue
            entries[field].append((value, location, kind))

    for kind in checklist:
        if kind not in seen_types:
            issue("blocker", "missing_document", f"Missing {kind.replace('_', ' ')} evidence.",
                  f"Add evidence for the {kind.replace('_', ' ')} requirement.")
        elif kind not in usable_types:
            issue("blocker", "no_usable_document", f"No usable {kind.replace('_', ' ')} evidence.",
                  "Replace the affected document with a complete, current copy.")

    def compare(field, left, right, code, evidence, raw, kinds):
        status = name_similarity(left, right) if field in NAME_FIELDS else (
            "exact_match" if left == right else "clear_mismatch"
        )
        languages = {detected_language(value) for value in raw} - {None, "Mixed"}
        verify_ocr = any(not item["user_confirmed"] and (
            item["confidence_band"] == "low" or item["date_format_uncertain"]
        ) for item in evidence)
        dates = [documents[item["document"] - 1].issued_on for item in evidence]
        different_periods = len(dates) == 2 and all(dates) and abs((dates[0] - dates[1]).days) >= 365
        historical_address = (scheme is None and field in ADDRESS_COMPARISON_FIELDS and left != right
                              and ("age" in kinds or different_periods))
        different_scripts = len(languages) > 1
        transliteration_match = (different_scripts and left != right and isinstance(left, str) and isinstance(right, str)
                                 and field in NAME_FIELDS | ADDRESS_COMPARISON_FIELDS | {"place_of_birth"}
                                 and " ".join(unidecode(left).casefold().split()) == " ".join(unidecode(right).casefold().split()))
        language_variation = different_scripts and (left == right or status == "likely_match")
        if verify_ocr or historical_address:
            classification = "needs_verification"
        elif language_variation:
            classification = "language_variation"
        elif transliteration_match:
            classification = "transliteration_match"
        elif status == "exact_match":
            classification = "exact_match" if raw[0] == raw[1] else "normalized_match"
        elif status == "likely_match":
            classification = "possible_match"
        elif status == "possible_mismatch":
            classification = "spelling_mismatch"
        else:
            classification = "actual_mismatch"
        compared_fields.add(field)
        comparisons.append({"status": status, "classification": classification, "comparison": code, "evidence": evidence})
        if classification in {"language_variation", "transliteration_match", "needs_verification"}:
            return
        if status == "likely_match":
            issue("warning", "name_variation", "The names appear to match with a variation.",
                  "Confirm the spelling or initials on the original documents.", evidence=evidence)
        elif status != "exact_match":
            conflicts.add(field)
            issue("warning", code, f"{field.replace('_', ' ').capitalize()} appears different.",
                  "Compare the originals and confirm which information is current.", evidence=evidence)

    for field, values in entries.items():
        profile_path = PROFILE_PATHS.get(field)
        profile_value = None
        if profile_path:
            section, key = profile_path
            saved = profile.get(section) or {}
            profile_value = normalized_value(field, saved.get(key))
        for position, (value, location, kind) in enumerate(values):
            evidence_field = documents[location["document"] - 1].fields[field]
            original = evidence_field.original_value or evidence_field.value
            if profile_value is not None:
                compare(field, value, profile_value, "profile_comparison", [location], [original, str(saved.get(key))], [kind])
            for other, other_location, other_kind in values[:position]:
                other_field = documents[other_location["document"] - 1].fields[field]
                compare(field, other, value, "cross_document", [other_location, location],
                        [other_field.original_value or other_field.value, original], [other_kind, kind])

    rule_set = None
    if scheme is not None:
        # Evaluate only unambiguous, applicable evidence. Preserve the saved profile.
        rule_profile = {section: dict(profile.get(section) or {}) for section, _ in PROFILE_PATHS.values()}
        rule_evidence = {}
        for field, kinds in RULE_DOCUMENT_TYPES.items():
            section, key = PROFILE_PATHS[field]
            candidates = [(value, location) for value, location, kind in entries[field] if kind in kinds]
            if field in conflicts or not candidates:
                rule_profile[section].pop(key, None)
                continue
            value, location = candidates[0]
            rule_profile[section][key] = float(value) if field == "annual_household_income" else value
            rule_evidence[field] = location

        dob = rule_profile["personal"].pop("date_of_birth", None)
        if dob is not None:
            rule_profile["age"] = age_on_date(dob, today)

        _, _, rule_set, evaluation, _ = evaluate_scheme(scheme, rule_profile)
        if scheme.scheme_id == "pb_old_age_pension":
            gender = str(rule_profile["personal"].get("gender", "")).casefold().strip()
            if gender not in {"male", "man", "female", "woman"} and "date_of_birth" in rule_evidence:
                issue("warning", "age_rule_needs_profile", "The Punjab age check needs the applicable profile answer.",
                      "Save the applicable gender answer in your profile to check the age requirement.",
                      evidence=[rule_evidence.pop("date_of_birth")])
        for condition in evaluation.conditions:
            field = RULE_FIELDS.get(condition.field)
            if evaluation.status == RuleStatus.FAIL and condition.status == RuleStatus.FAIL and field in rule_evidence:
                issue("blocker", "scheme_rule", condition.description,
                      "Review this evidence and confirm the current scheme requirements before applying.",
                      evidence=[rule_evidence[field]], source_url=condition.source_url)

    if checked_fields and not compared_fields:
        issue("information", "no_comparison", "No comparable values were available across the profile and documents.",
              "Save your profile answers or add evidence with the same field on another document.")

    if scheme and scheme.conditional_documents:
        issue("information", "conditional_documents", scheme.conditional_documents,
              "Check the scheme's official instructions for requirements that apply to you.")

    return {
        "scheme_id": scheme.scheme_id if scheme else None,
        "checklist_version": f"{scheme.last_checked}.v1" if scheme else None,
        "rule_set_version": rule_set.version if rule_set else None,
        "required_types": checklist,
        "document_count": len(documents),
        "fields_checked": checked_fields,
        "findings": findings,
        "comparisons": comparisons,
    }







