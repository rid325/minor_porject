from fastapi.testclient import TestClient
import httpx
import pytest

from backend.app.main import app
from backend.app.services import catalogue_chat as service

client = TestClient(app)
api = "/api/v1"


@pytest.fixture
def offline(monkeypatch):
    def unavailable(*args, **kwargs):
        raise httpx.ConnectError("offline")
    monkeypatch.setattr(service, "local_model", unavailable)
    service.vectors.cache_clear()


@pytest.mark.parametrize(("query", "expected"), [
    ("ਪੀਐਮ ਕਿਸਾਨ ਲਈ ਕਿਹੜੇ ਦਸਤਾਵੇਜ਼ ਚਾਹੀਦੇ ਹਨ?", "IN-PMKISAN-UMANG"),
    ("हरियाणा में वृद्धावस्था पेंशन के दस्तावेज़", "HR-OASA-002"),
    ("PM-KISAN in Punjab", "IN-PMKISAN-UMANG"),
    ("HIMCARE", "HP-HIMCARE-001"),
])
def test_retrieval_without_model(offline, query, expected):
    ref = client.post(api + "/chat", json={"message": query}).json()["references"][0]
    if "ਦਸਤਾਵੇ" in query or "दस्तावे" in query:
        assert ref["excerpt"] == client.get(api + "/schemes/" + expected).json()["documents_required"]
    assert ref["id"] == expected
    assert ref["source"].startswith("https://") and ref["checked"].startswith("2026-")


def test_confirmation_conflicts_and_token_isolation(offline):
    turn = client.post(api + "/chat", json={"message": "I am a farmer from Punjab"}).json()
    token = turn["session"]
    assert not turn["facts"] and turn["pending"]["location.state"] == "Punjab"
    def confirm(value):
        return client.post(api + "/chat", json={"session": token, "decision": "confirm", "field": "location.state", "value": value})
    assert confirm("Haryana").status_code == 409
    assert confirm("Punjab").json()["facts"]["location.state"] == "Punjab"
    client.post(api + "/chat", json={"session": token, "message": "I live in Haryana"})
    corrected = confirm("Haryana").json()
    assert corrected["changes"][-1]["previous"] == "Punjab"
    assert not client.post(api + "/chat", json={"message": "pension"}).json()["facts"]
    assert client.post(api + "/chat", json={"message": "pension", "session": "expired"}).status_code == 410


def test_all_checklists_and_reviewed_income_boundary():
    schemes = client.get(api + "/schemes?page_size=100").json()["items"]
    for s in schemes:
        data = client.get(api + "/schemes/" + s["scheme_id"] + "/document-checklist").json()
        assert data["instructions"] and data["source"]
    sid = "HR-LADLI-004"
    profile = {"household": {"household_annual_income": 200000, "only_daughters_no_sons": True},
               "scheme_answers": {sid: {f"custom.{sid}.parent_window": "yes", f"custom.{sid}.parent_connection": "yes"}}}
    def assess():
        return client.post(api + "/eligibility/check", json={"scheme_ids": [sid], "profile": profile}).json()["results"][0]
    assert assess()["category"] == "likely_eligible"
    profile["household"]["household_annual_income"] = 200001
    assert assess()["category"] == "likely_not_eligible"


def test_manual_checklist_preserves_conditions_and_rejects_stale_items(monkeypatch):
    from backend.app.api import auth_routes, document_routes
    monkeypatch.setattr(auth_routes.auth_service, "user_id_for_session", lambda _: "synthetic")
    monkeypatch.setattr(document_routes, "_saved_profile", lambda _: {})
    path = api + "/schemes/HR-MSYBC"
    checklist = client.get(path + "/document-checklist").json()
    assert any(item["section"] == "conditional" for item in checklist["items"])
    first = checklist["items"][0]["id"]
    request = {"consent": True, "documents": [], "preparation": {first: "missing"}}
    report = client.post(path + "/document-checks", json=request)
    assert report.status_code == 200
    assert report.json()["preparation"][0]["answer"] == "missing"
    request["preparation"] = {"outdated": "ready"}
    assert client.post(path + "/document-checks", json=request).status_code == 409


@pytest.mark.parametrize(("first", "second", "language", "word"), [
    ("हरियाणा वृद्धावस्था पेंशन के दस्तावेज़", "कौन से दस्तावेज़ चाहिए?", "hi", "आयु"),
    ("ਪੀਐਮ ਕਿਸਾਨ ਲਈ ਕਿਹੜੇ ਦਸਤਾਵੇਜ਼?", "Which documents?", "pa", "ਆਧਾਰ"),
])
def test_translated_followup_keeps_scheme_and_language(offline, first, second, language, word):
    first_turn = client.post(api + "/chat", json={"message": first}).json()
    followup = client.post(api + "/chat", json={"session": first_turn["session"], "message": second}).json()
    ref = followup["references"][0]
    assert ref["id"] == first_turn["references"][0]["id"]
    assert followup["language"] == language and followup["retrieval"] == "followup"
    assert word in ref["excerpt_translation"] and ref["conditional_translation"]
    assert ref["excerpt"] != ref["excerpt_translation"]


def test_state_search_keeps_nationwide_scheme_with_implementation_note(offline):
    result = client.post(api + "/chat", json={"message": "Pradhan Mantri Ujjwala Yojana 2.0 in Punjab"})
    assert result.json()["references"][0]["id"] == "central_pmuy_2"


def test_rural_employment_successor_keeps_existing_record_link():
    scheme = client.get(api + "/schemes/central_mgnrega_jobcard").json()
    assert "125 days" in scheme["summary"]
    assert "100 days" not in str(scheme)
    assert scheme["last_checked"] == "2026-11-24"


def test_profile_correction_and_dismissal_keep_scheme_for_application_followup(offline):
    records = {"message": "I am a farmer from Punjab. What documents do I need for PM KISAN?"}
    first = client.post(api + "/chat", json=records).json()
    token = first["session"]
    sid = first["references"][0]["id"]
    def turn(**fields):
        response = client.post(api + "/chat", json={"session": token, **fields})
        assert response.status_code == 200
        return response.json()
    turn(field="location.state", value="Punjab", decision="confirm")
    turn(field="agriculture.farmer_status", value="yes", decision="dismiss")
    correction = turn(message="I live in Haryana")
    assert correction["pending"] == {"location.state": "Haryana"}
    confirmed = turn(field="location.state", value="Haryana", decision="confirm")
    assert confirmed["facts"] == {"location.state": "Haryana"}
    application = turn(message="How do I apply?")
    assert application["references"][0]["id"] == sid == "IN-PMKISAN-UMANG"
    assert application["references"][0]["excerpt"] == client.get(api + "/schemes/" + sid).json()["application_steps"]


def test_reaffirming_confirmed_state_clears_pending_correction(offline):
    turn = client.post(api + "/chat", json={"message": "I live in Punjab"}).json()
    token = turn["session"]
    field = "location.state"
    client.post(api + "/chat", json={"session": token, "decision": "confirm", "field": field, "value": "Punjab"})
    client.post(api + "/chat", json={"session": token, "message": "I live in Haryana"})
    last = client.post(api + "/chat", json={"session": token, "message": "I live in Punjab"}).json()
    assert last["facts"][field] == "Punjab" and field not in last["pending"]
    assert client.post(api + "/chat", json={"session": token, "decision": "confirm", "field": field, "value": "Haryana"}).status_code == 409


def test_other_states_cannot_set_relevance_threshold(offline):
    from types import SimpleNamespace

    def pension(sid, name, region):
        return SimpleNamespace(scheme_id=sid, name=name, jurisdiction=region, category="Pension", summary="")
    records = [pension("A", "Senior Pension", "Haryana"), pension("B", "Widow Pension", "Punjab")]
    records.append(SimpleNamespace(scheme_id="C", name="Crop Insurance", jurisdiction="Punjab", category="Agriculture", summary=""))
    matches, _ = service.retrieve(records, "senior pension", state="Punjab")
    assert matches == [records[1]]
