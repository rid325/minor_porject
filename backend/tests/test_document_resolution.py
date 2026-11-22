import json

from fastapi.testclient import TestClient

from backend.app.api import auth_routes, document_routes
from backend.app.main import app
from backend.app.services import document_resolution


PATH = "/api/v1/schemes/HR-OASA-002/document-resolutions"
BODY = {
    "documents": [{"kind": "aadhaar", "value": "2002-05-10"}, {"kind": "birth", "value": "2002-05-15"}],
    "field": "date_of_birth",
}
PROFILE = {"location": {"state": "Haryana", "district": "Gurugram"}}


def signed_in(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.setattr(auth_routes.auth_service, "user_id_for_session", lambda token: "applicant")
    monkeypatch.setattr(document_routes.account_profile_service, "get_profile", lambda owner: {"profile": PROFILE})
    return TestClient(app)


def test_guide_without_ai_has_both_official_routes(monkeypatch):
    client = signed_in(monkeypatch)
    response = client.post(PATH, json=BODY)
    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    guide = response.json()
    assert guide["mode"] == "official_guidance"
    assert guide["difference_in_days"] == 5
    assert guide["first_action"].startswith("Confirm the correct value")
    assert any("gurugram.gov.in" in url for _, url in guide["routes"][1]["sources"])
    assert "2002-05-" not in response.text


def test_validated_ai_uses_only_minimized_context(monkeypatch):
    client = signed_in(monkeypatch)
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")

    def post(url, **options):
        assert url == "https://api.openai.com/v1/responses"
        payload = options["json"]
        assert payload["store"] is False
        assert payload["text"]["format"]["strict"] is True
        context = json.loads(payload["input"])
        assert context["difference_in_days"] == 5
        assert context["state"] == "haryana"
        assert context["district"] == "gurugram"
        assert context["document_types"] == ["Aadhaar Card", "Birth Certificate"]
        assert "2002-05-" not in payload["input"]
        return document_resolution.httpx.Response(200, request=document_resolution.httpx.Request("POST", url), json={
            "status": "completed", "output": [{"type": "message", "content": [
                {"type": "output_text", "text": '{"emphasis":"application","follow_up":"uidai_history"}'},
            ]}],
        })

    monkeypatch.setattr(document_resolution.httpx, "post", post)
    response = client.post(PATH, json={**BODY, "ai_consent": True, "verified_record": "first"})
    assert response.status_code == 200
    result = response.json()
    assert result["mode"] == "ai_assisted"
    assert result["routes"][0]["title"] == "If the birth register has the incorrect date"
    assert "Birth Certificate" in result["first_action"]


def test_invalid_provider_output_uses_retryable_official_guide(monkeypatch):
    client = signed_in(monkeypatch)
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.setattr(document_resolution.httpx, "post", lambda url, **kwargs: document_resolution.httpx.Response(
        200, request=document_resolution.httpx.Request("POST", url),
        json={"status": "completed", "output": [{"type": "message", "content": [
            {"type": "output_text", "text": '{"fee":"unverified fee"}'},
        ]}]},
    ))
    result = client.post(PATH, json={**BODY, "ai_consent": True}).json()
    assert result["retryable"] is True
    assert result["mode"] == "official_guidance"
    assert "unverified fee" not in str(result)


def test_resolution_requires_a_session_and_valid_mismatch(monkeypatch):
    monkeypatch.setattr(auth_routes.auth_service, "user_id_for_session", lambda token: None)
    assert TestClient(app).post(PATH, json=BODY).status_code == 401
    client = signed_in(monkeypatch)
    same = [{"kind": "aadhaar", "value": "2002-05-10"}, {"kind": "birth", "value": "2002-05-10"}]
    assert client.post(PATH, json={**BODY, "documents": same}).status_code == 422


def test_public_example_uses_fixed_values_without_account_or_provider(monkeypatch):
    def unexpected(*args):
        raise AssertionError("The public example must not use accounts or AI.")

    monkeypatch.setattr(auth_routes.auth_service, "user_id_for_session", unexpected)
    monkeypatch.setattr(document_resolution, "_ai_decision", unexpected)
    client = TestClient(app)
    detail = client.get("/api/v1/schemes/HR-OASA-002")
    assert detail.status_code == 200
    assert isinstance(detail.json()["application_guide"], dict)
    response = client.get(PATH.replace("document-resolutions", "document-resolution-example"))
    assert response.status_code == 200
    assert response.json()["guide"]["difference_in_days"] == 5
    assert response.json()["guide"]["mode"] == "official_guidance"


def test_standalone_checker_uses_signed_in_profile_without_a_scheme(monkeypatch):
    client = signed_in(monkeypatch)
    documents = [
        {"document_type": "residence", "fields": {"state": {"value": state, "page": 1}}}
        for state in ("Punjab", "Haryana")
    ]
    response = client.post("/api/v1/document-checks", json={"documents": documents, "consent": True})
    assert response.status_code == 200
    report = response.json()
    assert report["checklist_version"] is None
    assert report["required_types"] == []
    assert {item["code"] for item in report["findings"]} == {"profile_comparison", "cross_document"}
    assert client.get("/api/v1/document-resolution-example").json()["guide"]["difference_in_days"] == 5
    assert client.post("/api/v1/document-resolutions", json=BODY).status_code == 200


def test_standalone_upload_is_authenticated(monkeypatch):
    monkeypatch.setattr(auth_routes.auth_service, "user_id_for_session", lambda token: None)
    response = TestClient(app).post("/api/v1/document-extractions/identity", content=b"")
    assert response.status_code == 401



def test_gemini_generates_validated_decision_with_minimized_context(monkeypatch):
    client = signed_in(monkeypatch)
    monkeypatch.setenv("GEMINI_API_KEY", "fake-gemini-key")
    monkeypatch.setenv("GEMINI_RESOLUTION_MODEL", "gemini-test")
    monkeypatch.setenv("OPENAI_API_KEY", "fake-openai-key")

    def post(url, **options):
        assert url == "https://generativelanguage.googleapis.com/v1beta/models/gemini-test:generateContent"
        assert options["headers"] == {"x-goog-api-key": "fake-gemini-key"}
        payload = options["json"]
        context = json.loads(payload["contents"][0]["parts"][0]["text"])
        assert context["difference_in_days"] == 5
        assert "2002-05-" not in json.dumps(context)
        assert payload["generationConfig"]["responseJsonSchema"]["additionalProperties"] is False
        return document_resolution.httpx.Response(
            200, request=document_resolution.httpx.Request("POST", url),
            json={"candidates": [{"finishReason": "STOP", "content": {"parts": [
                {"text": '{"emphasis":"evidence","follow_up":"uidai_history"}'},
            ]}}]},
        )

    monkeypatch.setattr(document_resolution.httpx, "post", post)
    result = client.post(PATH, json={**BODY, "ai_consent": True}).json()
    assert result["mode"] == "ai_assisted"
    assert any("Aadhaar centre" in question for question in result["follow_ups"])


def test_profile_mismatch_uses_authenticated_saved_value(monkeypatch):
    client = signed_in(monkeypatch)
    monkeypatch.setattr(document_routes.account_profile_service, "get_profile",
                        lambda owner: {"profile": {"personal": {"date_of_birth": "2002-05-15"}}})
    response = client.post(PATH, json={
        "field": "date_of_birth",
        "documents": [{"kind": "aadhaar", "value": "2002-05-10"},
                      {"kind": "role_profile", "value": "2002-01-01"}],
        "verified_record": "first",
    })
    assert response.status_code == 200
    assert response.json()["difference_in_days"] == 5
    assert response.json()["profile_display_value"] == "2002-05-15"
    assert response.json()["first_action"].startswith("Review the corresponding field")


def test_gemini_gets_exact_values_only_with_explicit_consent(monkeypatch):
    from backend.app.schemas.document_resolution import GuideDecision, ResolutionRequest

    contexts = []
    monkeypatch.setattr(document_resolution, "_ai_decision", lambda context: contexts.append(context)
                        or GuideDecision(emphasis="evidence", follow_up="confirm_record"))
    for share in (False, True):
        request = ResolutionRequest.model_validate({**BODY, "ai_consent": True, "share_conflicting_values": share})
        document_resolution.build_resolution(request, None, PROFILE)
    assert "conflicting_values" not in contexts[0]
    assert contexts[1]["conflicting_values"] == ["2002-05-10", "2002-05-15"]

    address_request = ResolutionRequest.model_validate({
        "documents": [{"kind": "aadhaar", "value": "House 1"}, {"kind": "voter_id", "value": "House 2"}],
        "field": "address", "ai_consent": True, "share_conflicting_values": True,
    })
    document_resolution.build_resolution(address_request, None, PROFILE)
    assert "conflicting_values" not in contexts[-1]
