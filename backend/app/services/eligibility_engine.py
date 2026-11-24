"""Deterministic, explainable eligibility evaluation.

Only rules in ``RULE_SETS`` are labelled reviewed.  Every other catalogue
record remains browseable but is intentionally returned as ``information_only``
until its narrative criteria have been reviewed and encoded.  A missing answer
is always ``UNKNOWN``; it is never coerced to false or zero.
"""

from __future__ import annotations

from datetime import date, datetime, timezone
from functools import lru_cache
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
from pymongo.errors import PyMongoError
from .auth_service import AuthNotConfigured, get_database
from .condition_normalizer import fact_id_for_path


ENGINE_VERSION = "2.0"
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
PM_KISAN_GUIDELINES = "https://fw.pmkisan.gov.in/Documents/RevisedPM-KISANOperationalGuidelines%28English%29.pdf"
HARYANA_OLD_AGE = "https://sewa.haryana.gov.in/old-age-samman-allowance-scheme/"


def _reviewed(
    scheme_id: str,
    expression: dict[str, Any],
    source_url: str,
    *,
    reviewed_date: str = "2026-09-21",
    external_checks: list[str] | None = None,
) -> RuleSet:
    return RuleSet(
        scheme_id=scheme_id,
        version=f"{reviewed_date}.v1",
        review_state=RuleReviewState.REVIEWED,
        expression=expression,
        source_urls=[source_url],
        external_checks=external_checks or [],
        reviewed_at=f"{reviewed_date}T00:00:00Z",
    )


def _post_matric_disability(scheme_id: str) -> RuleSet:
    source = "https://depwd.gov.in/en/scholarship-post-matric/"
    def confirm(key: str, description: str):
        return _rule(key, f"custom.{scheme_id}.{key}", "equals", True, description=description)

    return _reviewed(scheme_id, _all(
        confirm("course", "The applicant is in class XI or XII, diploma, degree or postgraduate study."),
        _rule("nationality", "social.is_indian_citizen", "equals", True, description="The applicant is an Indian national."),
        _rule("percentage", "personal.disability_percentage", "gte", 40, description="Benchmark disability is at least 40 percent."),
        _rule("income", "household.household_annual_income", "lte", 250000, description="Annual family income is at most INR 250,000."),
        confirm("no_other_stipend", "The applicant receives no other post-matric scholarship or stipend."),
        confirm("family_limit", "This award would stay within the two-child family limit."),
    ), source, reviewed_date="2026-11-24",
        external_checks=["Confirm UDID, Aadhaar, applicable exceptions, enrolment year and current application window with the authority."])


# The first pilot rule set covers representative pension, insurance, banking,
# worker, agriculture and household schemes.  The remaining 60+ records stay
# visible but are deliberately not evaluated as if their narrative text were a
# verified machine rule.
RULE_SETS: dict[str, RuleSet] = {
    **{key: _post_matric_disability(key) for key in (
        "central_depwd_post_matric_scholarship_disabilities", "chd_post_matric_scholarship_students_disabilities"
    )},
    "HR-LADLI-004": _reviewed(
        "HR-LADLI-004",
        _all(
            _rule("ladli-daughters", "household.only_daughters_no_sons", "equals", True,
                  description="The family has daughters and no biological or adopted son."),
            _rule("ladli-income", "household.household_annual_income", "less_than_or_equal", 200000,
                  description="Gross annual family income from all sources is at most INR 200,000."),
            _rule("ladli-parents", "custom.HR-LADLI-004.parent_connection", "equals", True,
                  description="The biological parent or parents are domiciled in Haryana or work for the Haryana government."),
            _rule("ladli-window", "custom.HR-LADLI-004.parent_window", "equals", True,
                  description="The family is within the 15-year benefit period starting when either parent turns 45."),
        ),
        "https://sewa.haryana.gov.in/ladli-social-security-allowance-scheme/",
        reviewed_date="2026-11-24",
        external_checks=["Confirm the applicable parent, family record and enrolment period with Haryana SEWA."],
    ),
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
                "pm-kisan-land-record",
                "agriculture.pm_kisan_land_record_status",
                "in",
                ["single_owner", "joint_owner", "inherited_and_updated"],
                description="Applicant is part of a farmer family (husband, wife and minor children) that owns cultivable land recorded in the State/UT land records. A tenant/cultivator without recorded ownership does not meet this condition.",
                missing_reason="Select what the current State/UT land record shows for this farmer family.",
                source_url=PM_KISAN_GUIDELINES,
            ),
            _rule(
                "pm-kisan-institutional-landholder",
                "agriculture.pm_kisan_institutional_landholder",
                "equals",
                False,
                description="The landholder is not an institutional landholder.",
                missing_reason="Is this farmer-family land held by an institution rather than by the family?",
                source_url=PM_KISAN_GUIDELINES,
            ),
            _rule(
                "pm-kisan-constitutional-post",
                "personal.pm_kisan_constitutional_post_family",
                "equals",
                False,
                description="No member of the farmer family is a former or present holder of a constitutional post.",
                missing_reason="Has any member of this farmer family held a constitutional post?",
                source_url=PM_KISAN_GUIDELINES,
            ),
            _rule(
                "pm-kisan-elected-official",
                "personal.pm_kisan_elected_official_family",
                "equals",
                False,
                description="No member of the farmer family is a former or present minister, MP, MLA/MLC, municipal mayor or district panchayat chairperson.",
                missing_reason="Has any member of this farmer family held one of the elected or public offices listed in the scheme conditions?",
                source_url=PM_KISAN_GUIDELINES,
            ),
            _rule(
                "pm-kisan-government-employee",
                "employment.pm_kisan_non_exempt_government_employee_family",
                "equals",
                False,
                description="No member of the farmer family is a serving or retired Central/State Government, PSU, autonomous-institution or regular local-body employee, excluding MTS/Class IV/Group D staff.",
                missing_reason="Does any family member fall within the scheme’s non-exempt serving/retired government-employee category?",
                source_url=PM_KISAN_GUIDELINES,
            ),
            _rule(
                "pm-kisan-pension",
                "household.pm_kisan_pension_10000_family",
                "equals",
                False,
                description="No member of the farmer family receives a monthly pension of INR 10,000 or more from the covered government-employee category (MTS/Class IV/Group D exceptions apply).",
                missing_reason="Does any family member receive a pension of INR 10,000 or more per month from a covered government service?",
                source_url=PM_KISAN_GUIDELINES,
            ),
            _rule(
                "pm-kisan-income-tax",
                "household.pm_kisan_income_tax_payer_family",
                "equals",
                False,
                description="No member of the farmer family paid income tax in the last assessment year.",
                missing_reason="Did any member of this farmer family pay income tax in the last assessment year?",
                source_url=PM_KISAN_GUIDELINES,
            ),
            _rule(
                "pm-kisan-practicing-professional",
                "employment.pm_kisan_practicing_professional_family",
                "equals",
                False,
                description="No member of the farmer family is a registered practicing doctor, engineer, lawyer, chartered accountant or architect.",
                missing_reason="Does any family member practise a profession listed in the scheme exclusions while registered with its professional body?",
                source_url=PM_KISAN_GUIDELINES,
            ),
            _rule(
                "pm-kisan-nri-family",
                "location.pm_kisan_nri_family",
                "equals",
                False,
                description="The new-beneficiary farmer family is not an NRI family under the Income Tax Act.",
                missing_reason="Is this farmer family classified as non-resident under the Income Tax Act?",
                source_url=PM_KISAN_GUIDELINES,
            ),
        ),
        PM_KISAN_GUIDELINES,
        external_checks=[
            "State/UT authorities verify the land record, family details, exclusion self-declaration, Aadhaar/e-KYC and bank linkage. This pre-screen cannot verify those official records."
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
                source_url=HARYANA_OLD_AGE,
            ),
            _rule(
                "hr-oasa-government-pension",
                "household.receives_government_pension",
                "equals",
                False,
                description="Applicant does not receive pension from a Government/Local/Statutory Body or substantially government-funded organization; the department also counts provident-fund income and annuities in its pension definition.",
                missing_reason="Do you receive pension from a government or local/statutory body, a substantially government-funded organization, a provident fund or an annuity?",
                source_url=HARYANA_OLD_AGE,
            ),
        ),
        HARYANA_OLD_AGE,
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


@lru_cache(maxsize=1)
def _database_rule_sets() -> dict[str, RuleSet]:
    try:
        documents = list(get_database().scheme_rules.find({}, {"_id": 0}))
    except (AuthNotConfigured, PyMongoError):
        return {}
    result: dict[str, RuleSet] = {}
    for document in documents:
        try:
            state = RuleReviewState(document.get("review_state", "UNRESOLVED"))
        except ValueError:
            state = RuleReviewState.UNRESOLVED
        result[document["scheme_id"]] = RuleSet(
            scheme_id=document["scheme_id"],
            version=str(document.get("version") or ENGINE_VERSION),
            review_state=state,
            expression=document.get("expression"),
            source_urls=document.get("source_urls") or [],
            external_checks=document.get("external_checks") or [],
            reviewed_at=document.get("reviewed_at"),
        )
    return result


def get_rule_set(scheme_id: str) -> RuleSet | None:
    stored = _database_rule_sets().get(scheme_id)
    reviewed = RULE_SETS.get(scheme_id)
    if reviewed and (not stored or stored.review_state != RuleReviewState.REVIEWED
                     or str(reviewed.reviewed_at or "") > str(stored.reviewed_at or "")):
        return reviewed
    return stored or reviewed


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
    if path in {"age", "personal.age"}:
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
        if explicit is not None:
            return explicit
        facts = values.get("facts") or {}
        return facts.get("personal.age") or values.get("age")
    current: Any = values
    for segment in path.split("."):
        if isinstance(current, Mapping):
            current = current.get(segment)
        else:
            current = getattr(current, segment, None)
        if current is None:
            break
    if current is None:
        facts = values.get("facts") or {}
        current = facts.get(fact_id_for_path(path))
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
            conditions = _most_relevant_alternatives(children)
        elif any(child.status == RuleStatus.EXTERNAL_CHECK for child in children):
            status = RuleStatus.EXTERNAL_CHECK
            conditions = _most_relevant_alternatives(children)
        else:
            status = RuleStatus.FAIL
            conditions = _most_relevant_alternatives(children)
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



def requirement_group_counts(expression: dict[str, Any] | None, profile: ApplicantProfile | Mapping[str, Any]) -> tuple[int, int]:
    """Count satisfied logical requirements, treating each OR expression as one group."""
    if not expression:
        return 0, 0
    if "all" in expression:
        values = [requirement_group_counts(child, profile) for child in expression["all"]]
        return sum(item[0] for item in values), sum(item[1] for item in values)
    summary = _evaluate_expression(expression, profile)
    total = 1
    matched = 1 if summary.status == RuleStatus.PASS else 0
    return matched, total

def _most_relevant_alternatives(
    alternatives: list[EvaluationSummary],
) -> list[AtomicEvaluation]:
    """Show the closest OR branch instead of making every alternative look required.

    If an applicant's known answers clearly fit one branch better (for example,
    a man evaluated against the men's age threshold), the other branch is
    irrelevant to their result and should not appear as a failed requirement.
    Tied branches remain visible when the profile cannot distinguish them.
    """
    if not alternatives:
        return []

    def score(summary: EvaluationSummary) -> tuple[int, int]:
        passed = sum(item.status == RuleStatus.PASS for item in summary.conditions)
        failed = sum(item.status == RuleStatus.FAIL for item in summary.conditions)
        return passed, -failed

    scores = [score(summary) for summary in alternatives]
    best = max(scores)
    selected = [summary for summary, candidate in zip(alternatives, scores) if candidate == best]
    return [item for summary in selected for item in summary.conditions]


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
    if not rule_set or not rule_set.expression or rule_set.review_state not in {RuleReviewState.REVIEWED, RuleReviewState.DEMO}:
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
    if rule_set.review_state == RuleReviewState.DEMO:
        category = EligibilityCategory.INFORMATION_ONLY
        warnings.append("Confirm current criteria with the administering authority before relying on this result.")
    if scheme.application_ready.value != "YES":
        warnings.append(
            f"Application route is marked {scheme.application_ready.value.title()} in the research register; confirm the caution before applying."
        )
    return category, rule_set.review_state, rule_set, summary, warnings
