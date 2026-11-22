from datetime import date

from fastapi.testclient import TestClient
import pytest

from backend.app.api import auth_routes, document_routes
from backend.app.main import app
from backend.app.schemas.document_checks import DocumentEvidence
from backend.app.services.document_checker import check_documents


TODAY = date(2026, 11, 21)
SCHEME = "HR-OASA-002"


def run(*documents, profile=None):
    return check_documents(
        document_routes.repository.get(SCHEME),
        [DocumentEvidence.model_validate(item) for item in documents],
        profile or {},
        TODAY,
    )


def field(value, **metadata):
    return {"value": value, "page": 2, **metadata}


def test_missing_expired_and_unknown_evidence():
    result = run(
        {"document_type": "bank", "expires_on": "2026-11-20"},
        {"document_type": "unknown"},
    )
    assert result["checklist_version"] == "2026-09-22.v1"
    assert [(item["code"], item["severity"]) for item in result["findings"][:5]] == [
        ("expired_document", "blocker"),
        ("unknown_type", "warning"),
        ("missing_document", "blocker"),
        ("missing_document", "blocker"),
        ("no_usable_document", "blocker"),
    ]


def test_rule_boundaries_and_low_confidence_evidence():
    result = run(
        {"document_type": "age", "fields": {"date_of_birth": field("1966-11-21")}},
        {"document_type": "residence", "fields": {"state": field("Punjab", ocr_confidence=0.65,
                                                               extraction_confidence=0.99)}},
        {"document_type": "income", "fields": {"annual_household_income": field("300,001")}},
    )
    rule_failures = [item for item in result["findings"] if item["code"] == "scheme_rule"]
    assert [item["evidence"][0]["field"] for item in rule_failures] == ["annual_household_income"]
    warning = next(item for item in result["findings"] if item["code"] == "confirm_field")
    assert warning["evidence"][0]["ocr_confidence"] == 0.65


def test_standalone_can_compare_unconfirmed_ocr_with_review_warning():
    documents = [
        DocumentEvidence.model_validate({
            "document_type": "age",
            "fields": {"date_of_birth": field(value, ocr_confidence=0.69)},
        })
        for value in ("2000-11-21", "2000-11-22")
    ]
    assert not check_documents(None, documents, {}, TODAY)["comparisons"]
    result = check_documents(None, documents, {}, TODAY, compare_unconfirmed=True)
    assert result["comparisons"][0]["status"] == "clear_mismatch"
    assert result["comparisons"][0]["classification"] == "needs_verification"
    assert any(item["code"] == "confirm_field" for item in result["findings"])


@pytest.mark.parametrize(("left", "right"), [
    ("Rahul Kumar", "राहुल कुमार"),
    ("Rahul Kumar", "ਰਾਹੁਲ ਕੁਮਾਰ"),
    ("राहुल कुमार", "ਰਾਹੁਲ ਕੁਮਾਰ"),
])
def test_cross_script_names_are_language_variations(left, right):
    documents = [DocumentEvidence.model_validate({"document_type": "identity", "fields": {"name": field(value)}})
                 for value in (left, right)]
    report = check_documents(None, documents, {}, TODAY)
    assert report["comparisons"][0]["classification"] == "language_variation"
    assert not any(item["code"] == "cross_document" for item in report["findings"])


def test_older_addresses_require_verification():
    documents = [DocumentEvidence.model_validate({
        "document_type": "identity", "issued_on": issued, "fields": {"address": field(address)},
    }) for issued, address in (("2010-01-01", "House 15"), ("2026-01-01", "House 25"))]
    report = check_documents(None, documents, {}, TODAY)
    assert report["comparisons"][0]["classification"] == "needs_verification"


def test_standalone_compares_address_with_house_number_and_pin():
    documents = [
        DocumentEvidence.model_validate({
            "document_type": kind,
            "fields": {"address": field(address), "pin": field("122001")},
        })
        for kind, address in (
            ("identity", "House 12, Gurugram, 122001"),
            ("residence", "House 21, Gurugram, 122001"),
        )
    ]
    result = check_documents(None, documents, {}, TODAY)
    assert {comparison["evidence"][0]["field"]: comparison["status"] for comparison in result["comparisons"]} == {
        "address": "clear_mismatch",
        "pin": "exact_match",
    }


def test_cross_document_conflict_withholds_rule_and_omits_values():
    result = run(
        {"document_type": "age", "fields": {"date_of_birth": field("2000-11-21")}},
        {"document_type": "family_id", "fields": {"date_of_birth": field("1965-11-21")}},
        profile={"personal": {"date_of_birth": "1965-11-21"}},
    )
    codes = {item["code"] for item in result["findings"]}
    assert {"cross_document", "profile_comparison"} <= codes
    assert "scheme_rule" not in codes
    assert "2000-11-21" not in str(result)


def test_api_requires_session_and_redacts_validation_errors(monkeypatch):
    monkeypatch.setattr(auth_routes.auth_service, "user_id_for_session", lambda token: None)
    client = TestClient(app)
    route = "/api/v1/schemes/" + SCHEME
    assert client.get(route + "/document-checklist").status_code == 200
    assert client.post(route + "/document-checks", json={"consent": True, "documents": []}).status_code == 401
    response = client.post(route + "/document-checks", json={
        "consent": True,
        "documents": [{"document_type": "identity", "identity_number": "123456789012"}],
    })
    assert response.status_code == 422
    assert "123456789012" not in response.text


def test_api_uses_signed_in_users_saved_profile(monkeypatch):
    monkeypatch.setattr(auth_routes.auth_service, "user_id_for_session", lambda token: "applicant")
    calls = []

    def load_profile(user_id):
        calls.append(user_id)
        return {"profile": {"location": {"state": "Haryana"}}}

    monkeypatch.setattr(document_routes.account_profile_service, "get_profile", load_profile)
    response = TestClient(app).post(
        "/api/v1/schemes/" + SCHEME + "/document-checks",
        json={"consent": True, "documents": [
            {"document_type": "residence", "fields": {"state": field("Punjab")}},
        ]},
    )
    assert response.status_code == 200
    assert calls == ["applicant"]
    assert "profile_comparison" in {issue["code"] for issue in response.json()["findings"]}
