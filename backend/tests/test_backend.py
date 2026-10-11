from __future__ import annotations

from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app.models.domain import EligibilityCategory
from backend.app.schemas.profile import ApplicantProfile
from backend.app.services.eligibility_engine import evaluate_scheme
from backend.app.services.scheme_service import SchemeRepository


client = TestClient(app)


def test_workbook_catalogue_has_expected_counts() -> None:
    response = client.get("/api/v1/schemes?page_size=100")
    assert response.status_code == 200
    payload = response.json()
    assert payload["total"] == 75
    assert len(payload["items"]) == 75

    counts = {"YES": 0, "CONDITIONAL": 0, "NO": 0}
    for item in payload["items"]:
        counts[item["application_readiness"]] += 1
    assert counts == {"YES": 28, "CONDITIONAL": 24, "NO": 23}


def test_missing_information_is_not_rejection() -> None:
    response = client.post(
        "/api/v1/eligibility/check",
        json={"scheme_ids": ["central_pmjjby"], "profile": {}},
    )
    assert response.status_code == 200
    result = response.json()["results"][0]
    assert result["category"] == EligibilityCategory.NEEDS_MORE_INFORMATION.value
    assert result["missing"]
    assert not result["failed"]


def test_pmjjby_age_boundaries_and_bank_rule() -> None:
    eligible = {
        "profile": {
            "personal": {"date_of_birth": "1980-01-01"},
            "social": {"has_savings_bank_account": True},
        },
        "scheme_ids": ["central_pmjjby"],
    }
    # On 2026-10-11 this person is 46 and within 18..50.
    response = client.post("/api/v1/eligibility/check", json=eligible)
    assert response.json()["results"][0]["category"] == EligibilityCategory.LIKELY_ELIGIBLE.value

    too_old = {
        **eligible,
        "profile": {
            "personal": {"date_of_birth": "1970-01-01"},
            "social": {"has_savings_bank_account": True},
        },
    }
    response = client.post("/api/v1/eligibility/check", json=too_old)
    assert response.json()["results"][0]["category"] == EligibilityCategory.LIKELY_NOT_ELIGIBLE.value


def test_any_branch_does_not_report_unselected_failure() -> None:
    profile = ApplicantProfile.model_validate(
        {
            "location": {"state": "Punjab"},
            "personal": {"date_of_birth": "1960-01-01", "gender": "female"},
            "household": {"household_annual_income": 50000},
        }
    )
    repository = SchemeRepository()
    category, _, _, summary, _ = evaluate_scheme(
        repository.get("pb_old_age_pension"), profile
    )
    assert category == EligibilityCategory.LIKELY_ELIGIBLE
    assert all(
        condition.rule_id not in {"pb-old-age-man-age", "pb-old-age-man-age-limit"}
        for condition in summary.conditions
    )


def test_unknown_scheme_is_information_only() -> None:
    response = client.post(
        "/api/v1/eligibility/check",
        json={"scheme_ids": ["central_ab_pmjay"], "profile": {}},
    )
    assert response.status_code == 200
    result = response.json()["results"][0]
    assert result["category"] == EligibilityCategory.INFORMATION_ONLY.value
    assert result["rule_review_state"] == "UNRESOLVED"


def test_profile_schema_and_health() -> None:
    health = client.get("/api/v1/health")
    assert health.status_code == 200
    assert health.json()["scheme_count"] == 75
    profile_schema = client.get("/api/v1/profile/schema")
    assert profile_schema.status_code == 200
    assert profile_schema.json()["schema_version"] == "1.0"
    assert any(section["key"] == "location" for section in profile_schema.json()["sections"])
