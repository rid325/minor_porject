"""Deterministic, explainable eligibility evaluation.

Only rules in ``RULE_SETS`` are labelled reviewed.  Every other catalogue
record remains browseable but is intentionally returned as ``information_only``
until its narrative criteria have been reviewed and encoded.  A missing answer
is always ``UNKNOWN``; it is never coerced to false or zero.
"""

from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Any, Mapping

from ..models.domain import (
    AtomicEvaluation,
    EligibilityCategory,
    EvaluationSummary,
    RuleReviewState,
    RuleSet,
    RuleStatus,
    SchemeRecord,
    age_on_date,
)
from ..schemas.profile import ApplicantProfile


ENGINE_VERSION = "1.0"
UNKNOWN_VALUES = {
    "",
    "unknown",
    "i do not know",
    "dont_know",
    "do_not_know",
    "prefer not to say",
    "prefer_not_to_say",
    "not_sure",
    "na",
    "n/a",
    "null",
    "none",
}


def _rule(
    rule_id: str,
    field: str,
    operator: str,
    value: Any = None,
    *,
    description: str,
    missing_reason: str | None = None,
    failure_reason: str | None = None,
    source_url: str | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "rule_id": rule_id,
        "field": field,
        "operator": operator,
        "description": description,
        "missing_reason": missing_reason
        or f"Tell us whether {field.replace('_', ' ')} meets this condition.",
        "failure_reason": failure_reason
        or f"The supplied value does not meet: {description}.",
    }
    if value is not None:
        payload["value"] = value
    if source_url:
        payload["source_url"] = source_url
    return payload


def _all(*expressions: dict[str, Any]) -> dict[str, Any]:
    return {"all": list(expressions)}


def _any(*expressions: dict[str, Any]) -> dict[str, Any]:
    return {"any": list(expressions)}


PMJJBY = "https://financialservices.gov.in/beta/sites/default/files/2023-10/PMJJBY.pdf"
PMSBY = "https://financialservices.gov.in/beta/sites/default/files/2023-10/PMSBY.pdf"
APY = "https://pfrda.org.in/web/pfrda/w/atal-pension-yojana"
PM_SYM = "https://labour.gov.in/pm-sym"
E_SHRAM = "https://eshram.gov.in/"
PMJDY = "https://financialservices.gov.in/beta/en/jan-dhan"
PMUY = "https://www.pmuy.gov.in/"
SSA = "https://www.indiapost.gov.in/documents/offerings/schemesandservices/posb/SukanyaSamriddhiAccountScheme2019English.pdf"
PMFBY = "https://pmfby.gov.in/"
PM_SURYA = "https://pmsuryaghar.gov.in/"
PM_KISAN = "https://pmkisan.gov.in/"


def _reviewed(
    scheme_id: str,
    expression: dict[str, Any],
    source_url: str,
    *,
    external_checks: list[str] | None = None,
) -> RuleSet:
    return RuleSet(
        scheme_id=scheme_id,
        version="2026-09-21.v1",
        review_state=RuleReviewState.REVIEWED,
        expression=expression,
        source_urls=[source_url],
        external_checks=external_checks or [],
        reviewed_at="2026-09-21T00:00:00Z",
    )


# The first pilot rule set covers representative pension, insurance, banking,
# worker, agriculture and household schemes.  The remaining 60+ records stay
# visible but are deliberately not evaluated as if their narrative text were a
# verified machine rule.
RULE_SETS: dict[str, RuleSet] = {
    "central_pmjjby": _reviewed(
        "central_pmjjby",
        _all(
            _rule(
                "pmjjby-age",
                "age",
                "greater_than_or_equal",
                18,
                description="Applicant is at least 18 years old.",
                missing_reason="Add the applicant's date of birth.",
                source_url=PMJJBY,
            ),
            _rule(
                "pmjjby-age-upper",
                "age",
                "less_than_or_equal",
                50,
                description="Applicant is no older than 50 years for new enrolment.",
                missing_reason="Add the applicant's date of birth.",
                source_url=PMJJBY,
            ),
            _rule(
                "pmjjby-bank-account",
                "social.has_savings_bank_account",
                "equals",
                True,
                description="Applicant has an eligible savings bank or post-office account.",
                missing_reason="Tell us whether the applicant has a savings bank or post-office account.",
                source_url=PMJJBY,
            ),
        ),
        PMJJBY,
        external_checks=[
            "The participating bank/post office must confirm account, consent and auto-debit details."
        ],
    ),
    "central_pmsby": _reviewed(
        "central_pmsby",
        _all(
            _rule(
                "pmsby-age",
                "age",
                "greater_than_or_equal",
                18,
                description="Applicant is at least 18 years old.",
                missing_reason="Add the applicant's date of birth.",
                source_url=PMSBY,
            ),
            _rule(
                "pmsby-age-upper",
                "age",
                "less_than_or_equal",
                70,
                description="Applicant is no older than 70 years for enrolment.",
                missing_reason="Add the applicant's date of birth.",
                source_url=PMSBY,
            ),
            _rule(
                "pmsby-bank-account",
                "social.has_savings_bank_account",
                "equals",
                True,
                description="Applicant has an eligible savings bank or post-office account.",
                missing_reason="Tell us whether the applicant has a savings bank or post-office account.",
                source_url=PMSBY,
            ),
        ),
        PMSBY,
        external_checks=[
            "Only one participating account may be used and the bank must confirm consent/auto-debit."
        ],
    ),
    "central_apy": _reviewed(
        "central_apy",
        _all(
            _rule(
                "apy-age",
                "age",
                "greater_than_or_equal",
                18,
                description="Applicant is at least 18 years old.",
                missing_reason="Add the applicant's date of birth.",
                source_url=APY,
            ),
            _rule(
                "apy-age-upper",
                "age",
                "less_than_or_equal",
                40,
                description="Applicant is no older than 40 years for joining.",
                missing_reason="Add the applicant's date of birth.",
                source_url=APY,
            ),
            _rule(
                "apy-bank-account",
                "social.has_savings_bank_account",
                "equals",
                True,
                description="Applicant has a savings bank or post-office savings account.",
                missing_reason="Tell us whether the applicant has a savings bank or post-office account.",
                source_url=APY,
            ),
            _rule(
                "apy-income-tax",
                "employment.income_tax_payer",
                "equals",
                False,
                description="Applicant is not an income-tax payer on the application date.",
                missing_reason="Tell us whether the applicant is an income-tax payer.",
                source_url=APY,
            ),
        ),
        APY,
        external_checks=[
            "The bank/post office must confirm account status and current APY onboarding rules."
        ],
    ),
    "central_pm_sym": _reviewed(
        "central_pm_sym",
        _all(
            _rule(
                "pm-sym-age",
                "age",
                "greater_than_or_equal",
                18,
                description="Applicant is at least 18 years old.",
                missing_reason="Add the applicant's date of birth.",
                source_url=PM_SYM,
            ),
            _rule(
                "pm-sym-age-upper",
                "age",
                "less_than_or_equal",
                40,
                description="Applicant is no older than 40 years for joining.",
                missing_reason="Add the applicant's date of birth.",
                source_url=PM_SYM,
            ),
            _rule(
                "pm-sym-worker",
                "employment.unorganised_worker",
                "equals",
                True,
                description="Applicant is an unorganised worker.",
                missing_reason="Tell us whether the applicant is an unorganised worker.",
                source_url=PM_SYM,
            ),
            _rule(
                "pm-sym-monthly-income",
                "employment.monthly_income",
                "less_than_or_equal",
                15000,
                description="Applicant's monthly income is no more than INR 15,000.",
                missing_reason="Add the applicant's monthly income.",
                source_url=PM_SYM,
            ),
            _rule(
                "pm-sym-income-tax",
                "employment.income_tax_payer",
                "equals",
                False,
                description="Applicant is not an income-tax payer.",
                missing_reason="Tell us whether the applicant is an income-tax payer.",
                source_url=PM_SYM,
            ),
            _rule(
                "pm-sym-epfo",
                "employment.epfo_member",
                "equals",
                False,
                description="Applicant is not covered by EPFO.",
                missing_reason="Tell us whether the applicant is covered by EPFO.",
                source_url=PM_SYM,
            ),
            _rule(
                "pm-sym-esic",
                "employment.esic_member",
                "equals",
                False,
                description="Applicant is not covered by ESIC.",
                missing_reason="Tell us whether the applicant is covered by ESIC.",
                source_url=PM_SYM,
            ),
        ),
        PM_SYM,
        external_checks=[
            "The enrolment centre must confirm the contribution and current exclusion checks."
        ],
    ),
    "central_eshram": _reviewed(
        "central_eshram",
        _all(
            _rule(
                "eshram-age",
                "age",
                "greater_than_or_equal",
                16,
                description="Applicant is at least 16 years old.",
                missing_reason="Add the applicant's date of birth.",
                source_url=E_SHRAM,
            ),
            _rule(
                "eshram-age-upper",
                "age",
                "less_than_or_equal",
                59,
                description="Applicant is no older than 59 years for registration.",
                missing_reason="Add the applicant's date of birth.",
                source_url=E_SHRAM,
            ),
            _rule(
                "eshram-worker",
                "employment.unorganised_worker",
                "equals",
                True,
                description="Applicant is an unorganised worker.",
                missing_reason="Tell us whether the applicant is an unorganised worker.",
                source_url=E_SHRAM,
            ),
            _rule(
                "eshram-income-tax",
                "employment.income_tax_payer",
                "equals",
                False,
                description="Applicant is not an income-tax payer.",
                missing_reason="Tell us whether the applicant is an income-tax payer.",
                source_url=E_SHRAM,
            ),
            _rule(
                "eshram-epfo",
                "employment.epfo_member",
                "equals",
                False,
                description="Applicant is not an EPFO member.",
                missing_reason="Tell us whether the applicant is an EPFO member.",
                source_url=E_SHRAM,
            ),
            _rule(
                "eshram-esic",
                "employment.esic_member",
                "equals",
                False,
                description="Applicant is not an ESIC member.",
                missing_reason="Tell us whether the applicant is an ESIC member.",
                source_url=E_SHRAM,
            ),
        ),
        E_SHRAM,
        external_checks=["Aadhaar and Aadhaar-linked mobile verification is completed on the official portal."],
    ),
    "central_pmjdy": _reviewed(
        "central_pmjdy",
        _all(
            _rule(
                "pmjdy-no-existing-account",
                "social.has_other_bank_account",
                "equals",
                False,
                description="Applicant does not already have another bank account for the basic-account route.",
                missing_reason="Tell us whether the applicant already has another bank account.",
                source_url=PMJDY,
            ),
        ),
        PMJDY,
        external_checks=["The bank/Bank Mitra must complete KYC and confirm the account route."],
    ),
    "central_pmuy_2": _reviewed(
        "central_pmuy_2",
        _all(
            _rule(
                "pmuy-adult-woman",
                "personal.gender",
                "in",
                ["female", "woman", "female/woman"],
                description="Applicant is an adult woman.",
                missing_reason="Tell us the applicant's gender for this scheme-specific condition.",
                source_url=PMUY,
            ),
            _rule(
                "pmuy-age",
                "age",
                "greater_than_or_equal",
                18,
                description="Applicant is at least 18 years old.",
                missing_reason="Add the applicant's date of birth.",
                source_url=PMUY,
            ),
            _rule(
                "pmuy-no-lpg",
                "household.has_lpg_connection",
                "equals",
                False,
                description="The household does not already have an LPG connection.",
                missing_reason="Tell us whether the household already has an LPG connection.",
                source_url=PMUY,
            ),
            _rule(
                "pmuy-poor-household",
                "household.poverty_category",
                "exists",
                description="Household belongs to a notified PMUY deprivation/category route.",
                missing_reason="Select the household's applicable PMUY deprivation/category route, or say that it is unknown.",
                source_url=PMUY,
            ),
        ),
        PMUY,
        external_checks=[
            "The LPG distributor must verify the notified category/deprivation declaration and household records."
        ],
    ),
    "central_sukanya_samriddhi": _reviewed(
        "central_sukanya_samriddhi",
        _all(
            _rule(
                "ssa-girl-child",
                "personal.gender",
                "in",
                ["female", "girl", "girl_child"],
                description="The beneficiary is a girl child.",
                missing_reason="Tell us the beneficiary's gender for this child account.",
                source_url=SSA,
            ),
            _rule(
                "ssa-age",
                "age",
                "less_than_or_equal",
                9,
                description="The girl has not attained age 10 on the opening date.",
                missing_reason="Add the beneficiary's date of birth.",
                source_url=SSA,
            ),
            _rule(
                "ssa-resident-indian",
                "location.country",
                "equals",
                "India",
                description="The beneficiary is a resident Indian citizen.",
                missing_reason="Tell us the beneficiary's country/residency.",
                source_url=SSA,
            ),
        ),
        SSA,
        external_checks=[
            "The post office/bank must check guardian, duplicate-account and family-limit exceptions."
        ],
    ),
    "central_pmfby": _reviewed(
        "central_pmfby",
        _all(
            _rule(
                "pmfby-farmer",
                "agriculture.farmer_status",
                "equals",
                True,
                description="Applicant is a farmer with an insurable crop interest.",
                missing_reason="Tell us whether the applicant is a farmer.",
                source_url=PMFBY,
            ),
            _rule(
                "pmfby-insurable-interest",
                "agriculture.insurable_crop_interest",
                "equals",
                True,
                description="Applicant has an insurable interest in the crop/area.",
                missing_reason="Tell us whether the applicant has an insurable crop interest.",
                source_url=PMFBY,
            ),
            _rule(
                "pmfby-notified-crop",
                "agriculture.crop_notified",
                "equals",
                True,
                description="The crop and area are notified for the relevant season.",
                missing_reason="Check whether the crop and area are notified for the season.",
                source_url=PMFBY,
            ),
        ),
        PMFBY,
        external_checks=[
            "State crop notification, insurer, season cut-off and tenancy proof must be confirmed externally."
        ],
    ),
    "central_pm_surya_ghar": _reviewed(
        "central_pm_surya_ghar",
        _all(
            _rule(
                "surya-residential-electricity",
                "social.residential_electricity_connection",
                "equals",
                True,
                description="Applicant has an eligible residential DISCOM electricity connection.",
                missing_reason="Tell us whether the electricity connection is residential and eligible.",
                source_url=PM_SURYA,
            ),
            _rule(
                "surya-consumer-type",
                "social.electricity_consumer_type",
                "in",
                ["residential", "domestic", "household"],
                description="The electricity connection is a residential/domestic connection.",
                missing_reason="Select the electricity consumer type.",
                source_url=PM_SURYA,
            ),
        ),
        PM_SURYA,
        external_checks=[
            "DISCOM approval, empanelled vendor, inspection, net-metering and current CFA rules must be confirmed."
        ],
    ),
    "IN-PMKISAN-UMANG": _reviewed(
        "IN-PMKISAN-UMANG",
        _all(
            _rule(
                "pm-kisan-farmer",
                "agriculture.farmer_status",
                "equals",
                True,
                description="Applicant belongs to a farmer family with cultivable land/eligible farmer interest.",
                missing_reason="Tell us whether the applicant is an eligible farmer.",
                source_url=PM_KISAN,
            ),
            _rule(
                "pm-kisan-land-record",
                "agriculture.landholding_status",
                "in",
                ["owner", "landholder", "cultivator", "tenant"],
                description="The applicant has a recognized cultivable-land or farmer record.",
                missing_reason="Select the applicant's landholding/cultivation status.",
                source_url=PM_KISAN,
            ),
        ),
        PM_KISAN,
        external_checks=[
            "State land-record seeding, Aadhaar e-KYC, bank validation and scheme exclusions are checked by the authorities."
        ],
    ),
    "HR-OASA-002": _reviewed(
        "HR-OASA-002",
        _all(
            _rule(
                "hr-oasa-state",
                "location.state",
                "equals",
                "Haryana",
                description="Applicant is resident/domiciled in Haryana.",
                missing_reason="Select the applicant's state.",
            ),
            _rule(
                "hr-oasa-age",
                "age",
                "greater_than_or_equal",
                60,
                description="Applicant is at least 60 years old.",
                missing_reason="Add the applicant's date of birth.",
            ),
            _rule(
                "hr-oasa-income",
                "household.household_annual_income",
                "less_than_or_equal",
                300000,
                description="Applicant and spouse combined annual income is no more than INR 3,00,000.",
                missing_reason="Add the combined annual income of the applicant and spouse.",
            ),
        ),
        "https://socialjusticehry.gov.in/",
        external_checks=[
            "PPP/CRID and pension/annuity records must be checked for the current proactive-service route."
        ],
    ),
    "HP-IGNWPS": _reviewed(
        "HP-IGNWPS",
        _all(
            _rule(
                "hp-widow-state",
                "location.state",
                "equals",
                "Himachal Pradesh",
                description="Applicant is resident/domiciled in Himachal Pradesh.",
                missing_reason="Select the applicant's state.",
            ),
            _rule(
                "hp-widow-status",
                "personal.is_widow",
                "equals",
                True,
                description="Applicant is a widow.",
                missing_reason="Tell us whether the applicant is a widow.",
            ),
            _rule(
                "hp-widow-age",
                "age",
                "greater_than_or_equal",
                40,
                description="Applicant is at least 40 years old.",
                missing_reason="Add the applicant's date of birth.",
            ),
            _rule(
                "hp-widow-age-upper",
                "age",
                "less_than_or_equal",
                79,
                description="Applicant is no older than 79 years under the reviewed route.",
                missing_reason="Add the applicant's date of birth.",
            ),
            _rule(
                "hp-widow-bpl",
                "household.is_bpl",
                "equals",
                True,
                description="Applicant belongs to a Below Poverty Line family.",
                missing_reason="Tell us whether the applicant has current BPL status.",
            ),
        ),
        "https://esomsa.hp.gov.in/?q=social-security-pension",
        external_checks=[
            "The district office must confirm the current age band, BPL record and local document checklist."
        ],
    ),
    "pb_old_age_pension": _reviewed(
        "pb_old_age_pension",
        _all(
            _rule(
                "pb-old-age-state",
                "location.state",
                "equals",
                "Punjab",
                description="Applicant is resident/domiciled in Punjab.",
                missing_reason="Select the applicant's state.",
            ),
            _any(
                _all(
                    _rule(
                        "pb-old-age-man-age",
                        "personal.gender",
                        "in",
                        ["male", "man"],
                        description="Applicant is a man.",
                        missing_reason="Tell us the applicant's gender.",
                    ),
                    _rule(
                        "pb-old-age-man-age-limit",
                        "age",
                        "greater_than_or_equal",
                        65,
                        description="Applicant is at least 65 years old under the men's age threshold.",
                        missing_reason="Add the applicant's date of birth.",
                    ),
                ),
                _all(
                    _rule(
                        "pb-old-age-woman-age",
                        "personal.gender",
                        "in",
                        ["female", "woman"],
                        description="Applicant is a woman.",
                        missing_reason="Tell us the applicant's gender.",
                    ),
                    _rule(
                        "pb-old-age-woman-age-limit",
                        "age",
                        "greater_than_or_equal",
                        58,
                        description="Applicant is at least 58 years old under the women's age threshold.",
                        missing_reason="Add the applicant's date of birth.",
                    ),
                ),
            ),
            _rule(
                "pb-old-age-income",
                "household.household_annual_income",
                "less_than_or_equal",
                60000,
                description="Total annual income from all sources is no more than INR 60,000.",
                missing_reason="Add total annual household/applicant income from all sources.",
            ),
        ),
        "https://punjab.gov.in/government/departments/social-security1/",
        external_checks=[
            "The district Social Security office must confirm residence, age/income documents and current service route."
        ],
    ),
}


def get_rule_set(scheme_id: str) -> RuleSet | None:
    return RULE_SETS.get(scheme_id)


def _unknown(value: Any) -> bool:
    if value is None:
        return True
    if isinstance(value, str):
        return value.strip().casefold() in UNKNOWN_VALUES
    return False


def _normalise(value: Any) -> Any:
    if isinstance(value, str):
        stripped = value.strip()
        if stripped.casefold() in {"true", "yes", "y", "1"}:
            return True
        if stripped.casefold() in {"false", "no", "n", "0"}:
            return False
        return stripped.casefold()
    return value


def _number(value: Any) -> float | None:
    if _unknown(value):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _profile_dict(profile: ApplicantProfile | Mapping[str, Any]) -> dict[str, Any]:
    if isinstance(profile, ApplicantProfile):
        return profile.model_dump(mode="python", exclude_none=False)
    return dict(profile)


def _value_at(profile: ApplicantProfile | Mapping[str, Any], path: str) -> Any:
    values = _profile_dict(profile)
    if path == "age":
        explicit = values.get("age")
        personal = values.get("personal") or {}
        dob = personal.get("date_of_birth")
        if isinstance(dob, str):
            try:
                dob = date.fromisoformat(dob)
            except ValueError:
                dob = None
        if isinstance(dob, date):
            return age_on_date(dob)
        return explicit
    current: Any = values
    for segment in path.split("."):
        if isinstance(current, Mapping):
            current = current.get(segment)
        else:
            current = getattr(current, segment, None)
        if current is None:
            break
    return current


def _compare(operator: str, actual: Any, expected: Any) -> RuleStatus:
    if operator == "exists":
        return RuleStatus.PASS if not _unknown(actual) else RuleStatus.UNKNOWN
    if _unknown(actual):
        return RuleStatus.UNKNOWN
    normalized_actual = _normalise(actual)
    normalized_expected = _normalise(expected)
    if operator == "equals":
        if isinstance(normalized_actual, str) and isinstance(normalized_expected, str):
            return RuleStatus.PASS if normalized_actual == normalized_expected else RuleStatus.FAIL
        return RuleStatus.PASS if normalized_actual == normalized_expected else RuleStatus.FAIL
    if operator == "in":
        values = normalized_expected if isinstance(normalized_expected, list) else [normalized_expected]
        values = [_normalise(item) for item in values]
        if isinstance(normalized_actual, list):
            return RuleStatus.PASS if any(_normalise(item) in values for item in normalized_actual) else RuleStatus.FAIL
        return RuleStatus.PASS if normalized_actual in values else RuleStatus.FAIL
    if operator == "contains":
        if isinstance(normalized_actual, (list, tuple, set)):
            return RuleStatus.PASS if normalized_expected in normalized_actual else RuleStatus.FAIL
        return RuleStatus.PASS if str(normalized_expected) in str(normalized_actual) else RuleStatus.FAIL
    if operator in {"greater_than_or_equal", "gte", "less_than_or_equal", "lte", "greater_than", "gt", "less_than", "lt"}:
        left = _number(normalized_actual)
        right = _number(normalized_expected)
        if left is None or right is None:
            return RuleStatus.FAIL
        if operator in {"greater_than_or_equal", "gte"}:
            passed = left >= right
        elif operator in {"less_than_or_equal", "lte"}:
            passed = left <= right
        elif operator in {"greater_than", "gt"}:
            passed = left > right
        else:
            passed = left < right
        return RuleStatus.PASS if passed else RuleStatus.FAIL
    if operator == "external_check":
        return RuleStatus.EXTERNAL_CHECK
    raise ValueError(f"Unsupported eligibility operator: {operator}")


def _evaluate_expression(
    expression: dict[str, Any], profile: ApplicantProfile | Mapping[str, Any]
) -> EvaluationSummary:
    if "all" in expression:
        children = [
            _evaluate_expression(child, profile) for child in expression["all"]
        ]
        conditions = [item for child in children for item in child.conditions]
        if any(child.status == RuleStatus.FAIL for child in children):
            status = RuleStatus.FAIL
        elif any(child.status == RuleStatus.UNKNOWN for child in children):
            status = RuleStatus.UNKNOWN
        elif any(child.status == RuleStatus.EXTERNAL_CHECK for child in children):
            status = RuleStatus.PASS
        else:
            status = RuleStatus.PASS
        return EvaluationSummary(status=status, conditions=conditions)
    if "any" in expression:
        children = [
            _evaluate_expression(child, profile) for child in expression["any"]
        ]
        passing_child = next(
            (child for child in children if child.status == RuleStatus.PASS), None
        )
        if passing_child is not None:
            status = RuleStatus.PASS
            # Once an alternative satisfies an ``any`` group, expose the
            # successful branch only.  Reporting failed conditions from an
            # unselected alternative would contradict the scheme result.
            conditions = passing_child.conditions
        elif any(child.status == RuleStatus.UNKNOWN for child in children):
            status = RuleStatus.UNKNOWN
            conditions = [item for child in children for item in child.conditions]
        elif any(child.status == RuleStatus.EXTERNAL_CHECK for child in children):
            status = RuleStatus.EXTERNAL_CHECK
            conditions = [item for child in children for item in child.conditions]
        else:
            status = RuleStatus.FAIL
            conditions = [item for child in children for item in child.conditions]
        return EvaluationSummary(status=status, conditions=conditions)
    if "not" in expression:
        child = _evaluate_expression(expression["not"], profile)
        if child.status == RuleStatus.PASS:
            status = RuleStatus.FAIL
        elif child.status == RuleStatus.FAIL:
            status = RuleStatus.PASS
        else:
            status = child.status
        return EvaluationSummary(status=status, conditions=child.conditions)

    field = expression.get("field")
    operator = expression.get("operator")
    actual = _value_at(profile, field) if field else None
    status = _compare(operator, actual, expression.get("value"))
    return EvaluationSummary(
        status=status,
        conditions=[
            AtomicEvaluation(
                rule_id=expression.get("rule_id", field or "rule"),
                status=status,
                field=field,
                description=expression.get("description"),
                actual_value=actual,
                expected_value=expression.get("value"),
                source_url=expression.get("source_url"),
                missing_reason=expression.get("missing_reason") if status == RuleStatus.UNKNOWN else None,
                failure_reason=expression.get("failure_reason") if status == RuleStatus.FAIL else None,
            )
        ],
    )


def _deduplicate(conditions: list[AtomicEvaluation]) -> list[AtomicEvaluation]:
    seen: set[str] = set()
    result: list[AtomicEvaluation] = []
    for condition in conditions:
        key = condition.rule_id
        if key in seen:
            continue
        seen.add(key)
        result.append(condition)
    return result


def evaluate_scheme(
    scheme: SchemeRecord,
    profile: ApplicantProfile | Mapping[str, Any],
) -> tuple[EligibilityCategory, RuleReviewState, RuleSet | None, EvaluationSummary, list[str]]:
    """Evaluate one scheme and return category plus explainable conditions."""

    rule_set = get_rule_set(scheme.scheme_id)
    if not rule_set or not rule_set.expression or rule_set.review_state != RuleReviewState.REVIEWED:
        return (
            EligibilityCategory.INFORMATION_ONLY,
            rule_set.review_state if rule_set else RuleReviewState.UNRESOLVED,
            rule_set,
            EvaluationSummary(status=RuleStatus.EXTERNAL_CHECK),
            [
                "Eligibility criteria have not yet been converted into a reviewed rule set for this prototype.",
                "Use the official source and application route shown on the scheme record.",
            ],
        )

    summary = _evaluate_expression(rule_set.expression, profile)
    summary.conditions = _deduplicate(summary.conditions)
    for condition in summary.conditions:
        if not condition.source_url and rule_set.source_urls:
            condition.source_url = rule_set.source_urls[0]
    if summary.status == RuleStatus.FAIL:
        category = EligibilityCategory.LIKELY_NOT_ELIGIBLE
    elif summary.status == RuleStatus.UNKNOWN:
        category = EligibilityCategory.NEEDS_MORE_INFORMATION
    else:
        category = EligibilityCategory.LIKELY_ELIGIBLE
    warnings = list(rule_set.external_checks)
    if scheme.application_ready.value != "YES":
        warnings.append(
            f"Application route is marked {scheme.application_ready.value.title()} in the research register; confirm the caution before applying."
        )
    return category, rule_set.review_state, rule_set, summary, warnings
