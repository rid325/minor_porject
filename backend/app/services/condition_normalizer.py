"""Source-preserving normalization for scheme eligibility criteria.

Narrative criteria are split into atomic requirements and mapped to reusable
applicant facts where the meaning is explicit. Ambiguous requirements remain
scheme-scoped draft facts; they are never used to reject an applicant.
"""
from __future__ import annotations

import hashlib
import re
from typing import Any

SCHEMA_VERSION = "2.0"

# IDs are stable semantic facts. Income scopes are deliberately distinct.
ATTRIBUTE_LABELS: dict[str, dict[str, Any]] = {
    "personal.date_of_birth": {"label": "Date of birth", "type": "date", "section": "personal", "sensitive": True},
    "personal.age": {"label": "Age in completed years", "type": "number", "section": "personal", "derived_from": "personal.date_of_birth"},
    "personal.gender": {"label": "Gender", "type": "enum", "section": "personal", "options": ["woman", "man", "non_binary", "other", "prefer_not_to_say"]},
    "personal.marital_status": {"label": "Marital status", "type": "enum", "section": "personal"},
    "personal.is_widow": {"label": "Is a widow", "type": "boolean", "section": "personal"},
    "personal.is_orphan": {"label": "Is an orphan", "type": "boolean", "section": "personal"},
    "personal.dependent_status": {"label": "Dependent status", "type": "text", "section": "personal"},
    "personal.disability_status": {"label": "Has a disability", "type": "boolean", "section": "personal"},
    "personal.disability_percentage": {"label": "Disability percentage", "type": "number", "section": "personal"},
    "location.state": {"label": "State or union territory", "type": "state", "section": "location"},
    "location.district": {"label": "District", "type": "text", "section": "location"},
    "location.residence_type": {"label": "Rural or urban residence", "type": "enum", "section": "location"},
    "location.domicile_status": {"label": "Domicile/residency status", "type": "boolean", "section": "location"},
    "household.household_annual_income": {"label": "Total household/family annual income", "type": "currency_inr", "section": "household", "scope": "household"},
    "household.applicant_annual_income": {"label": "Applicant annual income", "type": "currency_inr", "section": "household", "scope": "applicant"},
    "household.applicant_spouse_annual_income": {"label": "Applicant and spouse combined annual income", "type": "currency_inr", "section": "household", "scope": "applicant_and_spouse"},
    "household.parent_guardian_annual_income": {"label": "Parent/guardian annual income", "type": "currency_inr", "section": "household", "scope": "parent_or_guardian"},
    "household.size": {"label": "Household size", "type": "number", "section": "household"},
    "household.is_bpl": {"label": "Has Below Poverty Line status", "type": "boolean", "section": "household"},
    "household.ration_card_type": {"label": "Ration card category", "type": "enum", "section": "household"},
    "household.ppp_status": {"label": "Parivar Pehchan Patra status", "type": "enum", "section": "household"},
    "household.ppp_annual_income": {"label": "Verified PPP annual income", "type": "currency_inr", "section": "household"},
    "household.has_lpg_connection": {"label": "Household has an LPG connection", "type": "boolean", "section": "household"},
    "household.has_pucca_house": {"label": "Household owns a pucca house", "type": "boolean", "section": "household"},
    "household.has_adult_children": {"label": "Has adult children", "type": "boolean", "section": "household"},
    "education.student_status": {"label": "Currently a student", "type": "boolean", "section": "education"},
    "education.study_level": {"label": "Current study level/course", "type": "text", "section": "education"},
    "education.institution_type": {"label": "Institution type", "type": "text", "section": "education"},
    "education.institution_approved": {"label": "Institution/course is recognized", "type": "boolean", "section": "education"},
    "employment.employment_status": {"label": "Employment status", "type": "enum", "section": "employment"},
    "employment.occupation": {"label": "Occupation", "type": "text", "section": "employment"},
    "employment.worker_category": {"label": "Worker category", "type": "text", "section": "employment"},
    "employment.worker_registration_status": {"label": "Required worker registration status", "type": "boolean", "section": "employment"},
    "employment.self_employed": {"label": "Self-employed", "type": "boolean", "section": "employment"},
    "employment.unorganised_worker": {"label": "Unorganised-sector worker", "type": "boolean", "section": "employment"},
    "employment.income_tax_payer": {"label": "Pays income tax", "type": "boolean", "section": "employment"},
    "employment.epfo_member": {"label": "EPFO member", "type": "boolean", "section": "employment"},
    "employment.esic_member": {"label": "ESIC member", "type": "boolean", "section": "employment"},
    "agriculture.farmer_status": {"label": "Member of a farmer family", "type": "boolean", "section": "agriculture"},
    "agriculture.landholding_status": {"label": "Landholding status", "type": "enum", "section": "agriculture"},
    "agriculture.cultivable_land_acres": {"label": "Cultivable land area in acres", "type": "number", "section": "agriculture"},
    "agriculture.land_record_status": {"label": "Name is present in land records", "type": "boolean", "section": "agriculture"},
    "agriculture.crop_notified": {"label": "Crop is notified for the area/season", "type": "boolean", "section": "agriculture"},
    "social.social_category": {"label": "Social category", "type": "enum", "section": "social", "options": ["general", "sc", "st", "obc", "other"]},
    "social.existing_benefits": {"label": "Existing government benefits", "type": "text", "section": "social"},
    "social.has_aadhaar": {"label": "Has Aadhaar", "type": "boolean", "section": "social"},
    "social.has_bank_account": {"label": "Has a bank account", "type": "boolean", "section": "social"},
    "social.has_savings_bank_account": {"label": "Has a savings bank/post-office account", "type": "boolean", "section": "social"},
    "social.has_mobile": {"label": "Has a mobile number", "type": "boolean", "section": "social"},
    "social.required_registration_status": {"label": "Required scheme/worker registration", "type": "boolean", "section": "social"},
    "social.disability_certificate_status": {"label": "Has valid disability certificate/UDID", "type": "boolean", "section": "social"},
    "social.secc_or_entitlement_listed": {"label": "Listed in required entitlement database", "type": "boolean", "section": "social"},
    "household.only_daughters_no_sons": {"label": "Family has daughter(s) and no son", "type": "boolean", "section": "household"},
    "household.parent_death_or_absence": {"label": "Parent deceased or regularly absent", "type": "boolean", "section": "household"},
    "household.parent_care_capacity": {"label": "Parent can provide care/support", "type": "boolean", "section": "household"},
    "social.is_indian_citizen": {"label": "Indian citizen/national", "type": "boolean", "section": "social"},
    "household.has_adult_children": {"label": "Has adult children", "type": "boolean", "section": "household"},
    "agriculture.has_cultivable_land": {"label": "Has cultivable land", "type": "boolean", "section": "agriculture"},
    "social.udyam_registration_status": {"label": "Udyam registration status", "type": "boolean", "section": "social"},
    "education.highest_qualification": {"label": "Highest qualification", "type": "text", "section": "education"},
    "location.pin": {"label": "Postal PIN code", "type": "text", "section": "location"},
    "location.country": {"label": "Country", "type": "text", "section": "location"},
    "personal.name": {"label": "Name", "type": "text", "section": "personal", "sensitive": True},
    "household.applicant_monthly_income": {"label": "Applicant monthly income", "type": "currency_inr", "section": "household", "scope": "applicant"},
    "household.income_period": {"label": "Income period", "type": "enum", "section": "household"},
    "household.currency": {"label": "Income currency", "type": "text", "section": "household"},
    "household.poverty_category": {"label": "Poverty category", "type": "text", "section": "household"},
    "education.course": {"label": "Course", "type": "text", "section": "education"},
    "education.highest_qualification": {"label": "Highest qualification", "type": "text", "section": "education"},
    "employment.enterprise_status": {"label": "Enterprise status", "type": "text", "section": "employment"},
    "employment.new_business": {"label": "Starting a new business", "type": "boolean", "section": "employment"},
    "employment.monthly_income": {"label": "Applicant employment monthly income", "type": "currency_inr", "section": "employment", "scope": "applicant"},
    "employment.government_nps_member": {"label": "Government NPS member", "type": "boolean", "section": "employment"},
    "agriculture.housing_status": {"label": "Housing status", "type": "text", "section": "agriculture"},
    "agriculture.owns_house": {"label": "Owns a house", "type": "boolean", "section": "agriculture"},
    "agriculture.insurable_crop_interest": {"label": "Has an insurable crop interest", "type": "boolean", "section": "agriculture"},
    "social.has_other_bank_account": {"label": "Has another eligible bank account", "type": "boolean", "section": "social"},
    "social.electricity_consumer_type": {"label": "Electricity consumer type", "type": "enum", "section": "social"},
    "social.residential_electricity_connection": {"label": "Has residential electricity connection", "type": "boolean", "section": "social"},
    "social.required_registration_status": {"label": "Required registration status", "type": "text", "section": "social"},
    "social.existing_benefits": {"label": "Existing benefits", "type": "text", "section": "social"},
}

ALIASES = {
    "personal.is_widow": "personal.is_widow",
    "location.domicile": "location.domicile_status",
    "household.applicant_income": "household.applicant_annual_income",
    "household.family_income": "household.household_annual_income",
    "household.bpl_status": "household.is_bpl",
    "household.ppp_income": "household.ppp_annual_income",
    "household.ration_card": "household.ration_card_type",
    "employment.worker_registration": "employment.worker_registration_status",
    "agriculture.cultivable_land": "agriculture.has_cultivable_land",
    "social.existing_benefit": "social.existing_benefits",
    "social.required_registration": "social.required_registration_status",
    "location.domicile_status": "location.domicile_status",
    "household.household_annual_income": "household.household_annual_income",
    "household.is_bpl": "household.is_bpl",
    "household.ration_card_type": "household.ration_card_type",
    "employment.income_tax_payer": "employment.income_tax_payer",
    "employment.worker_registration_status": "employment.worker_registration_status",
    "agriculture.cultivable_land_acres": "agriculture.cultivable_land_acres",
    "social.has_savings_bank_account": "social.has_savings_bank_account",
}


def fact_id_for_path(path: str) -> str:
    path = str(path or "").strip().strip(".")
    if path in {"age", "personal.age"}:
        return "personal.age"
    return ALIASES.get(path, path)


def empty_user_facts(attribute_ids: set[str] | None = None) -> dict[str, Any]:
    return {key: None for key in sorted(set(ATTRIBUTE_LABELS) | (attribute_ids or set()))}


def profile_facts_from_profile(profile: dict[str, Any], extra_ids: set[str] | None = None) -> dict[str, Any]:
    allowed_ids = set(ATTRIBUTE_LABELS) | (extra_ids or set())
    facts: dict[str, Any] = {}
    for section, values in profile.items():
        if not isinstance(values, dict):
            continue
        for key, value in values.items():
            if key == "scheme_answers" or key == "facts":
                continue
            path = fact_id_for_path(f"{section}.{key}")
            if path in allowed_ids:
                facts[path] = None if value == "" else value
    personal = profile.get("personal") or {}
    if "date_of_birth" in personal:
        facts["personal.date_of_birth"] = personal["date_of_birth"] or None
    for scheme_answers in (profile.get("scheme_answers") or {}).values():
        if not isinstance(scheme_answers, dict):
            continue
        for path, value in scheme_answers.items():
            fact_id = fact_id_for_path(path)
            if fact_id in allowed_ids:
                facts[fact_id] = None if value == "" else value
    supplied = profile.get("facts")
    if isinstance(supplied, dict):
        for key, value in supplied.items():
            if key in allowed_ids:
                facts[key] = value
    return facts


def _condition_id(attribute_id: str, operator: str, value: Any, scope: str | None = None) -> str:
    payload = f"{attribute_id}|{operator}|{value!r}|{scope or ''}".casefold()
    return "cond_" + hashlib.sha1(payload.encode("utf-8")).hexdigest()[:16]


def _mapped_clause(text: str, scheme_id: str, index: int) -> dict[str, Any]:
    clause = re.sub(r"\s+", " ", text).strip(" .;,:–—-")
    lower = clause.casefold()
    attribute = None
    operator = "is_described_by"
    value: Any = clause
    confidence = "unmapped"
    scope = None

    # Pull out each fact as an independent atom, with scope kept explicit.
    if re.search(r"\b(woman|women|female|girl|bride)\b", lower):
        attribute, operator, value, confidence = "personal.gender", "equals", "woman", "high"
    elif re.search(r"\b(man|men|male)\b", lower):
        attribute, operator, value, confidence = "personal.gender", "equals", "man", "high"
    elif re.search(r"\b(?:sc|scheduled caste)\b", lower):
        attribute, operator, value, confidence = "social.social_category", "in", ["sc"], "high"
    elif re.search(r"\b(?:st|scheduled tribe)\b", lower):
        attribute, operator, value, confidence = "social.social_category", "in", ["st"], "high"
    elif re.search(r"\b(?:obc|backward class(?:es)?)\b", lower):
        attribute, operator, value, confidence = "social.social_category", "in", ["obc"], "medium"
    elif "below poverty line" in lower or re.search(r"\bbpl\b", lower):
        attribute, operator, value, confidence = "household.is_bpl", "equals", True, "high"
    elif "widow" in lower:
        attribute, operator, value, confidence = "personal.is_widow", "equals", True, "high"
    elif "orphan" in lower:
        attribute, operator, value, confidence = "personal.is_orphan", "equals", True, "high"
    elif "parent" in lower and any(term in lower for term in ("died", "deceased", "dead")):
        attribute, operator, value, confidence = "household.parent_death_or_absence", "equals", True, "high"
    elif "parent" in lower and any(term in lower for term in ("absent", "incapacitated", "unable to care", "unable to support")):
        attribute, operator, value, confidence = "household.parent_care_capacity", "equals", False, "medium"
    elif "daughter" in lower or "no son" in lower:
        attribute, operator, value, confidence = "household.only_daughters_no_sons", "equals", True, "medium"
    elif "no adult children" in lower:
        attribute, operator, value, confidence = "household.has_adult_children", "equals", False, "high"
    elif "adult children" in lower:
        attribute, operator, value, confidence = "household.has_adult_children", "equals", True, "medium"
    elif "indian citizen" in lower or "indian national" in lower:
        attribute, operator, value, confidence = "social.is_indian_citizen", "equals", True, "high"
    elif "student" in lower or "enrolled" in lower or "studying" in lower:
        attribute, operator, value, confidence = "education.student_status", "equals", True, "medium"
    elif "cultivable land" in lower:
        attribute, operator, value, confidence = "agriculture.has_cultivable_land", "equals", True, "medium"
    elif "farmer" in lower or "landholding" in lower:
        attribute, operator, value, confidence = "agriculture.farmer_status", "equals", True, "medium"
    elif "lpg" in lower:
        attribute, operator, value, confidence = "household.has_lpg_connection", "equals", False, "medium"
    elif "pucca house" in lower or "no pucca house" in lower:
        attribute, operator, value, confidence = "household.has_pucca_house", "equals", "no pucca house" not in lower, "medium"
    elif "disability" in lower or "disabled" in lower:
        attribute, operator, value, confidence = "personal.disability_status", "equals", True, "medium"
    if ("disability" in lower or "udid" in lower or "permanent certificate" in lower) and any(term in lower for term in ("certificate", "udid")):
        attribute, operator, value, confidence = "social.disability_certificate_status", "equals", not any(term in lower for term in ("no ", "without", "not have")), "medium"
    elif "aadhaar" in lower:
        attribute, operator, value, confidence = "social.has_aadhaar", "equals", True, "medium"
    elif "bank account" in lower:
        attribute, operator, value, confidence = "social.has_bank_account", "equals", True, "medium"
    elif "ppp" in lower or "family id" in lower:
        attribute, operator, value, confidence = "household.ppp_status", "equals", "verified", "medium"
    elif "udyam" in lower:
        attribute, operator, value, confidence = "social.udyam_registration_status", "equals", True, "medium"
    elif "cultivable land" in lower:
        attribute, operator, value, confidence = "agriculture.has_cultivable_land", "equals", True, "medium"
    elif "no income ceiling" in lower:
        attribute, operator, value, confidence = "household.applicant_annual_income", "no_ceiling", None, "high"
    elif "new viable unit" in lower or "new unit" in lower:
        attribute, operator, value, confidence = "employment.new_business", "equals", True, "medium"
    elif "class 8 pass" in lower or "class viii pass" in lower:
        attribute, operator, value, confidence = "education.highest_qualification", "at_least", "class_8", "medium"

    states = {
        "haryana": "Haryana", "punjab": "Punjab", "himachal pradesh": "Himachal Pradesh",
        "chandigarh": "Chandigarh", "rajasthan": "Rajasthan", "uttar pradesh": "Uttar Pradesh",
        "uttarakhand": "Uttarakhand", "delhi": "Delhi", "maharashtra": "Maharashtra",
        "bihar": "Bihar", "gujarat": "Gujarat", "karnataka": "Karnataka", "kerala": "Kerala",
        "tamil nadu": "Tamil Nadu", "west bengal": "West Bengal", "odisha": "Odisha",
        "assam": "Assam", "jharkhand": "Jharkhand", "chhattisgarh": "Chhattisgarh",
        "madhya pradesh": "Madhya Pradesh", "goa": "Goa", "telangana": "Telangana",
        "andhra pradesh": "Andhra Pradesh", "manipur": "Manipur", "meghalaya": "Meghalaya",
        "mizoram": "Mizoram", "nagaland": "Nagaland", "tripura": "Tripura", "sikkim": "Sikkim",
        "arunachal pradesh": "Arunachal Pradesh", "jammu and kashmir": "Jammu and Kashmir",
        "ladakh": "Ladakh", "puducherry": "Puducherry", "andaman": "Andaman and Nicobar Islands",
    }
    matched_state = next((label for token, label in states.items() if token in lower), None)
    if matched_state and any(word in lower for word in ("resident", "domicile", "bona fide", "residence")):
        attribute, operator, value, confidence = "location.state", "equals", matched_state, "high"

    age_context = bool(re.search(r"\b(age|aged|years? old|years? of age|child|children|adult|adults)\b", lower) or re.search(r"\b(applicant|individual|person)\s+(?:is\s+)?(?:above|over|aged)\s+\d+", lower))
    if age_context:
        age_match = re.search(r"\b(?:aged?|age(?:d)?|age of)\s*(?:at least|minimum|not less than)?\s*(\d{1,3})\s*(?:years?)?\s*(?:to|[-–])\s*(\d{1,3})\b", lower)
        if age_match:
            attribute, operator, value, confidence = "personal.age", "greater_than_or_equal", int(age_match.group(1)), "high"
        else:
            age_match = re.search(r"\b(?:at least|minimum|min\.?|aged?\s+|age\s+|above|over)\s*(\d{1,3})\s*(?:years?\s+old|years? of age|years?)?\b", lower)
            if age_match:
                attribute, operator, value, confidence = "personal.age", "greater_than_or_equal", int(age_match.group(1)), "high"
            else:
                age_match = re.search(r"\b(?:below|under|less than)\s*(\d{1,3})(?:\s*years?)?\b", lower)
                if age_match:
                    attribute, operator, value, confidence = "personal.age", "less_than", int(age_match.group(1)), "high"
                else:
                    age_match = re.search(r"\b(?:no older than|at most|up to)\s*(\d{1,3})\s*years?\b", lower)
                    if age_match:
                        attribute, operator, value, confidence = "personal.age", "less_than_or_equal", int(age_match.group(1)), "high"

    disability_match = re.search(r"(?:at least|minimum|minimum of)\s*(\d{1,3})\s*(?:%|percent)", lower)
    if disability_match and ("disability" in lower or "disabled" in lower):
        attribute, operator, value, confidence = "personal.disability_percentage", "greater_than_or_equal", int(disability_match.group(1)), "medium"
    else:
        disability_match = re.search(r"(?:below|under|less than)\s*(\d{1,3})\s*(?:%|percent)", lower)
        if disability_match and ("disability" in lower or "disabled" in lower):
            attribute, operator, value, confidence = "personal.disability_percentage", "less_than", int(disability_match.group(1)), "medium"

    income_match = re.search(r"(?:income|earnings)[^.;]{0,100}?(up to|not more than|no more than|not exceeding|no higher than|does not exceed|maximum|max\.?|below|less than|<=|≤|above|over|more than|greater than|>)\s*(?:rs\.?|inr)?\s*([\d,]+(?:\.\d+)?)\s*(lakh(?:s)?|l\b|crore(?:s)?)?", lower)
    if income_match:
        amount = float(income_match.group(2).replace(",", ""))
        if income_match.group(3) in {"lakh", "lakhs", "l"}:
            amount *= 100000
        elif income_match.group(3) in {"crore", "crores"}:
            amount *= 10000000
        scope = "parent_or_guardian" if "parent" in lower or "guardian" in lower else "applicant_and_spouse" if "spouse" in lower else "household" if any(term in lower for term in ("family", "household")) else "applicant"
        attribute = {"household": "household.household_annual_income", "applicant": "household.applicant_annual_income", "applicant_and_spouse": "household.applicant_spouse_annual_income", "parent_or_guardian": "household.parent_guardian_annual_income"}[scope]
        income_relation = income_match.group(1)
        operator = "greater_than" if income_relation in {"above", "over", "more than", "greater than", ">"} else "less_than_or_equal"
        value, confidence = int(amount), "medium"

    if not attribute:
        # Preserve every unresolved clause as an addressable fact, scoped to this scheme.
        slug = re.sub(r"[^a-z0-9]+", "_", clause.casefold()).strip("_")[:42] or str(index)
        attribute = f"custom.{scheme_id}.{slug}_{index}"
        operator, value, confidence = "is_described_by", clause, "unresolved"

    return {
        "condition_id": _condition_id(attribute, operator, value, scope),
        "attribute_id": attribute,
        "operator": operator,
        "value": value,
        "scope": scope,
        "source_text": clause,
        "confidence": confidence,
        "display_label": clause,
        "review_state": "DRAFT",
    }


def split_criteria(text: str) -> list[tuple[str, str]]:
    """Split text into source-preserving clauses with conjunction/or context."""
    clauses: list[tuple[str, str]] = []
    for sentence in re.split(r"(?<=[.!?])\s+|[;\n•]+", text or ""):
        sentence = sentence.strip()
        if not sentence:
            continue
        sentence = re.sub(r",\s+(?=(?:and |or )?(?:no|not|income|gross|age|aged|has|have|holds|applicant|student|resident|domiciled|family|adult|owns|does|must|is|are|be|requires|with at least)\b)", " AND ", sentence, flags=re.IGNORECASE)
        parts = re.split(r"\s+(and|or)\s+", sentence, flags=re.IGNORECASE)
        pending_join = "AND"
        for part in parts:
            word = part.casefold()
            if word in {"and", "or"}:
                pending_join = word.upper()
                continue
            cleaned = part.strip(" .;,:–—-")
            if len(cleaned) >= 4:
                clauses.append((cleaned, pending_join))
                pending_join = "AND"
    return clauses


def _skip_custom_question(condition: dict[str, Any]) -> bool:
    text = re.sub(r"\s+", " ", str(condition.get("source_text") or "")).strip().casefold()
    text = re.sub(r"^(?:and|or|but)\s+", "", text)
    if len(text.split()) < 2 or text in {"income conditions", "applicable scheme rules", "other", "above", "below", "supplies", "marriage"}:
        return True
    note_phrases = (
        "current official page", "current department page", "official page does not",
        "current official page has", "research register", "scheme page says",
        "source says", "source states", "source materials", "historical target",
        "former condition", "former form", "official form", "published application form",
        "committee compliance", "verification control", "review/reassessment rules",
        "not a current published", "not published on", "not currently published",
        "may be revised", "rules may differ", "current rules may", "no exclusions list",
        "there is no family-size", "scheme expanded beyond", "a budget allocation",
        "the current economic survey", "current official sources", "confirm at district level",
    )
    return any(phrase in text for phrase in note_phrases)


def _missing_question(condition: dict[str, Any]) -> str:
    field = str(condition.get("attribute_id") or "")
    source = str(condition.get("source_text") or "this requirement").strip().rstrip(" .?!")
    source = re.sub(r"^(?:and|or|but)\s+", "", source, flags=re.IGNORECASE)
    if field.startswith("custom."):
        return f"Is this statement true for you: {source}?"
    questions = {
        "personal.age": "Age is calculated automatically from your date of birth in your profile.",
        "personal.gender": "Which gender option describes you?",
        "personal.marital_status": "What is your marital status?",
        "personal.is_widow": "Are you widowed?",
        "personal.is_orphan": "Is the applicant an orphan?",
        "personal.disability_status": "Do you have a disability?",
        "personal.disability_percentage": "What disability percentage is recorded on your certificate?",
        "location.state": "Which state or union territory do you live in?",
        "location.district": "Which district do you live in?",
        "location.residence_type": "Do you live in a rural or urban area?",
        "location.domicile_status": "Are you domiciled in this state?",
        "household.household_annual_income": "What is your household or family’s annual income?",
        "household.applicant_annual_income": "What is your annual income?",
        "household.applicant_monthly_income": "What is your monthly income?",
        "employment.monthly_income": "What is your monthly employment income?",
        "household.applicant_spouse_annual_income": "What is your and your spouse’s combined annual income?",
        "household.parent_guardian_annual_income": "What is your parent or guardian’s annual income?",
        "household.ppp_annual_income": "What annual income is recorded on your Parivar Pehchan Patra?",
        "household.size": "How many people live in your household?",
        "agriculture.cultivable_land_acres": "How many acres of cultivable land do you hold?",
        "household.is_bpl": "Does your household have a Below Poverty Line (BPL) status?",
        "household.ration_card_type": "Which ration card category does your household have?",
        "household.ppp_status": "What is your Parivar Pehchan Patra (PPP) status?",
        "household.has_lpg_connection": "Does your household have an LPG connection?",
        "household.only_daughters_no_sons": "Does your family have daughters and no sons?",
        "household.has_adult_children": "Do you have any adult children?",
        "household.parent_death_or_absence": "Is a parent deceased or regularly absent?",
        "household.parent_care_capacity": "Can the parent provide care and support?",
        "household.has_pucca_house": "Does your household own a pucca house?",
        "education.student_status": "Are you currently enrolled as a student?",
        "education.highest_qualification": "What is your highest completed qualification?",
        "education.study_level": "What is your current level of study?",
        "education.institution_type": "What type of institution do you attend?",
        "education.institution_approved": "Is your institution or course recognized?",
        "employment.employment_status": "What is your current employment status?",
        "employment.self_employed": "Are you self-employed?",
        "employment.new_business": "Are you starting a new business?",
        "employment.worker_registration_status": "Are you registered as a worker?",

        "employment.unorganised_worker": "Do you work in the unorganised sector?",
        "employment.income_tax_payer": "Do you currently pay income tax?",
        "employment.epfo_member": "Are you a member of EPFO?",
        "employment.esic_member": "Are you covered by ESIC?",
        "agriculture.farmer_status": "Are you part of a farmer family?",
        "agriculture.has_cultivable_land": "Do you have cultivable land?",
        "agriculture.landholding_status": "What is your landholding status?",

        "agriculture.crop_notified": "Is your crop notified for your area and season?",
        "social.social_category": "Which social category applies to you?",
        "social.has_aadhaar": "Do you have an Aadhaar number?",
        "social.has_bank_account": "Do you have a bank account?",
        "social.has_savings_bank_account": "Do you have a savings bank or post-office account?",
        "social.has_mobile": "Do you have a mobile number?",
        "social.required_registration_status": "Do you have the registration required for this scheme?",
        "social.udyam_registration_status": "Do you have an active Udyam registration?",
        "social.has_other_bank_account": "Do you have another bank account?",
        "social.disability_certificate_status": "Do you have a valid disability certificate or UDID?",
        "social.is_indian_citizen": "Are you an Indian citizen?",
        "social.residential_electricity_connection": "Does your home have a residential electricity connection?",
        "social.electricity_consumer_type": "Is your electricity connection residential or commercial?",
    }
    if field in questions:
        return questions[field]
    definition = ATTRIBUTE_LABELS.get(field, {})
    label = str(definition.get("label") or source).strip().rstrip(" .?!")
    value_type = definition.get("type")
    if value_type in {"currency_inr", "number"}:
        return f"What is {label.lower()}? Choose the closest listed amount."
    if value_type == "enum":
        return f"Which {label.lower()} option applies to you?"
    if value_type == "date":
        return f"What is your {label.lower()}?"
    return f"Is this statement true for you: {source}?"

def _prototype_expression(conditions: list[dict[str, Any]]) -> dict[str, Any] | None:
    """Build transparent prototype matching rules from eligibility text only.

    Canonical facts use their parsed operators. Unmapped applicant clauses become scheme-scoped yes/no questions. Exclusions are deliberately not inverted automatically because prose exclusion logic is too easy to misread.
    """
    supported = {
        "equals", "in", "contains", "greater_than_or_equal", "less_than_or_equal",
        "greater_than", "less_than", "exists",
    }
    groups: dict[int, list[dict[str, Any]]] = {}
    for condition in conditions:
        if condition.get("source_section") != "eligibility":
            continue
        operator = condition.get("operator")
        if operator == "no_ceiling":
            continue
        field = str(condition.get("attribute_id") or "")
        value = condition.get("value")
        is_custom = field.startswith("custom.") or condition.get("confidence") == "unresolved"
        if is_custom and _skip_custom_question(condition):
            continue
        if is_custom:
            operator, value = "equals", True
            missing_reason = _missing_question(condition)
            failure_reason = "Your answer does not meet this requirement."
            description = condition.get("normalized_label") or condition.get("source_text") or field
        elif operator in supported and value is not None:
            missing_reason = _missing_question(condition)
            failure_reason = f"Your answer does not meet: {condition.get('normalized_label') or condition.get('source_text', '')}."
            description = condition.get("normalized_label") or condition.get("source_text") or field
        else:
            continue
        groups.setdefault(int(condition.get("logic_group") or len(groups) + 1), []).append({
            "rule_id": condition.get("condition_id") or field,
            "field": field,
            "operator": operator,
            "value": value,
            "description": description,
            "missing_reason": missing_reason,
            "failure_reason": failure_reason,
            "prototype_rule": True,
            "joiner": condition.get("joiner", "AND"),
        })

    if not groups:
        return None
    logical_groups: list[dict[str, Any]] = []
    for group_id in sorted(groups):
        atoms = groups[group_id]
        if len(atoms) == 1:
            logical_groups.append(atoms[0])
        elif any(item.get("joiner") == "OR" for item in atoms):
            logical_groups.append({"any": atoms})
        else:
            logical_groups.append({"all": atoms})
    return logical_groups[0] if len(logical_groups) == 1 else {"all": logical_groups}


def normalize_scheme(record: dict[str, Any], reviewed_rules: dict[str, Any] | None = None) -> dict[str, Any]:
    scheme_id = str(record.get("scheme_id") or "unknown")
    conditions: list[dict[str, Any]] = []
    for source_section, text in (("eligibility", record.get("eligibility_text")), ("exclusions", record.get("exclusions_text"))):
        group = 0
        clauses = split_criteria(text or "")
        for index, (clause, joiner) in enumerate(clauses, 1):
            if index == 1 or joiner == "AND":
                group += 1
            atom = _mapped_clause(clause, scheme_id, index)
            atom["logic_group"] = group
            atom["joiner"] = joiner
            atom["source_section"] = source_section
            conditions.append(atom)
            age_range = re.search(r"\b(?:aged?|age(?:d)?|age of)\s*(?:at least|minimum)?\s*(\d{1,3})\s*(?:years?)?\s*(?:to|[-–])\s*(\d{1,3})\b", clause, re.IGNORECASE)
            if source_section == "eligibility" and age_range and atom["attribute_id"] == "personal.age":
                upper = int(age_range.group(2))
                conditions.append({
                    **atom,
                    "condition_id": _condition_id("personal.age", "less_than_or_equal", upper),
                    "operator": "less_than_or_equal",
                    "value": upper,
                    "source_text": f"Age is no more than {upper} years",
                    "display_label": f"Age is no more than {upper} years",
                    "joiner": "AND",
                })

    reviewed = reviewed_rules or {}
    if reviewed.get("expression") and reviewed.get("review_state") == "REVIEWED":
        atoms = []
        def collect(expression: dict[str, Any], group_path: str = "root"):
            if "all" in expression or "any" in expression:
                key = "all" if "all" in expression else "any"
                for child_index, child in enumerate(expression[key]):
                    collect(child, f"{group_path}.{key}.{child_index}")
                return
            if "not" in expression:
                collect(expression["not"], f"{group_path}.not")
                return
            path = str(expression.get("field") or "unmapped")
            attribute = fact_id_for_path(path)
            expected = expression.get("value")
            op = str(expression.get("operator") or "exists")
            atoms.append({
                "condition_id": _condition_id(attribute, op, expected),
                "attribute_id": attribute,
                "operator": op,
                "value": expected,
                "source_text": expression.get("description") or path,
                "display_label": expression.get("description") or path,
                "confidence": "reviewed",
                "review_state": "REVIEWED",
                "source_section": "reviewed_rule",
                "rule_id": expression.get("rule_id"),
                "expression_group": group_path,
            })
        collect(reviewed["expression"])
        if atoms:
            conditions = atoms

    prototype_expression = None if reviewed.get("review_state") == "REVIEWED" else _prototype_expression(conditions)
    state = "REVIEWED" if reviewed.get("review_state") == "REVIEWED" and conditions else "DEMO" if prototype_expression else "UNRESOLVED"
    operator_labels = {
        "equals": "is", "in": "is one of", "greater_than_or_equal": "is at least",
        "less_than_or_equal": "is at most", "less_than": "is below", "greater_than": "is above",
        "no_ceiling": "has no income ceiling in the published criterion",
        "at_least": "is at least", "is_described_by": "needs scheme-specific review",
    }
    for condition in conditions:
        condition["review_state"] = state if condition.get("source_section") != "reviewed_rule" else "REVIEWED"
        definition = ATTRIBUTE_LABELS.get(condition["attribute_id"], {})
        condition["attribute_label"] = definition.get("label", condition.get("source_text", condition["attribute_id"]))
        expected = condition.get("value")
        rendered = ", ".join(map(str, expected)) if isinstance(expected, list) else str(expected) if expected is not None else ""
        if condition.get("confidence") == "unresolved":
            condition["normalized_label"] = condition["attribute_label"]
        else:
            condition["normalized_label"] = " ".join(filter(None, [
                condition["attribute_label"], operator_labels.get(condition.get("operator"), condition.get("operator")), rendered
            ])).strip()

    extra_sources = record.get("additional_sources") or []
    if isinstance(extra_sources, str):
        extra_sources = extra_sources.split("|")
    source_urls = list(dict.fromkeys(item.strip() for item in [record.get("source_url"), *extra_sources] if isinstance(item, str) and item.strip()))
    external_checks = list(reviewed.get("external_checks") or [])
    if state == "DEMO":
        external_checks.append("Confirm current criteria with the administering authority before relying on this match.")
        if record.get("exclusions_text"):
            external_checks.append("Published exclusion text is shown separately and is not automatically evaluated by the matcher.")
    return {
        "scheme_id": scheme_id,
        "schema_version": SCHEMA_VERSION,
        "review_state": state,
        "normalized_conditions": conditions,
        "source_urls": source_urls,
        "source_eligibility_text": record.get("eligibility_text"),
        "source_exclusions_text": record.get("exclusions_text"),
        "unresolved_notes": record.get("eligibility_unresolved"),
        "expression": reviewed.get("expression") if state == "REVIEWED" else prototype_expression,
        "version": reviewed.get("version") or SCHEMA_VERSION,
        "reviewed_at": reviewed.get("reviewed_at"),
        "external_checks": external_checks,
    }


def build_catalog(records: list[dict[str, Any]], reviewed_rules: dict[str, Any] | None = None) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    schemes = [normalize_scheme(record, (reviewed_rules or {}).get(record.get("scheme_id"))) for record in records]
    attrs: dict[str, dict[str, Any]] = {}
    for attribute_id, definition in ATTRIBUTE_LABELS.items():
        attrs[attribute_id] = {"attribute_id": attribute_id, **definition, "schema_version": SCHEMA_VERSION}
    for scheme in schemes:
        for condition in scheme["normalized_conditions"]:
            attr = condition["attribute_id"]
            if attr not in attrs:
                attrs[attr] = {
                    "attribute_id": attr,
                    "label": condition["display_label"],
                    "type": "unknown",
                    "section": "scheme_specific",
                    "scheme_id": scheme["scheme_id"],
                    "requires_review": True,
                    "schema_version": SCHEMA_VERSION,
                }
    return schemes, list(attrs.values())


