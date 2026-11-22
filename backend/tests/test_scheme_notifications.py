from datetime import date
from types import SimpleNamespace

from backend.app.api.notification_routes import public_settings
from backend.app.services.scheme_matching import profile_for_scheme
from backend.app.services.scheme_notifications import scheme_alerts
from backend.app.models.domain import EligibilityCategory
from backend.app.services import scheme_notifications


def test_alerts_only_remind_within_deadline_window_and_skip_closed_matches():
    scheme = SimpleNamespace(name="Test scheme")
    today = date(2026, 11, 22)
    assert [event for event, *_ in scheme_alerts(scheme, None, today)] == ["match"]
    assert [event for event, *_ in scheme_alerts(scheme, date(2026, 11, 30), today)] == ["match"]
    assert [event for event, *_ in scheme_alerts(scheme, date(2026, 11, 29), today)] == [
        "match", "deadline:2026-11-29",
    ]
    assert not list(scheme_alerts(scheme, date(2026, 11, 21), today))


def test_alerts_require_a_verified_registered_email():
    email = "user@example.com"
    saved = {"sms_enabled": True, "scheme_email_enabled": True, "scheme_email_verified": "other@example.com"}
    assert public_settings(saved, email) == {
        "email": email, "email_verified": False, "email_enabled": False,
    }
    assert public_settings({**saved, "scheme_email_verified": email}, email) == {
        "email": email, "email_verified": True, "email_enabled": True,
    }


def test_scheme_specific_answers_do_not_change_other_matches():
    profile = {"location": {"state": "Punjab"}, "scheme_answers": {"test": {"location.state": "Haryana"}}}
    assert profile_for_scheme(profile, "test") == {"location": {"state": "Haryana"}}
    assert profile_for_scheme(profile, "other") == {"location": {"state": "Punjab"}}


def test_demo_inbox_matches_profile_without_sending_email(monkeypatch):
    schemes = [SimpleNamespace(scheme_id="match", name="Matching scheme"),
               SimpleNamespace(scheme_id="other", name="Other scheme")]
    monkeypatch.setattr(scheme_notifications, "evaluate_scheme", lambda scheme, profile: (
        EligibilityCategory.LIKELY_ELIGIBLE if scheme.scheme_id == "match"
        else EligibilityCategory.LIKELY_NOT_ELIGIBLE,
    ))
    from datetime import datetime
    today = datetime.now(scheme_notifications.INDIA).date()
    monkeypatch.setenv("SCHEME_NOTIFICATION_DEADLINES", f'{{"match":"{today}"}}')
    def unexpected_send(*args):
        raise AssertionError("The demo must never send email")
    monkeypatch.setattr(scheme_notifications, "send_email", unexpected_send)
    result = scheme_notifications.preview_alerts(SimpleNamespace(all=lambda: schemes), {"location": {"state": "Punjab"}})
    assert [message["title"] for message in result["messages"]] == ["New scheme match", "Application deadline"]
    assert all(message["scheme_path"] == "/schemes/match" for message in result["messages"])


def test_brevo_mail_uses_configured_sender_and_only_the_registered_recipient(monkeypatch):
    monkeypatch.setenv("BREVO_API_KEY", "test-key")
    monkeypatch.setenv("NOTIFICATION_EMAIL_FROM", "alerts@example.com")
    calls = []

    def capture(url, **request):
        calls.append((url, request))
        return SimpleNamespace(raise_for_status=lambda: None)

    monkeypatch.setattr(scheme_notifications.httpx, "post", capture)
    scheme_notifications.send_email("user@example.com", "New scheme match", "Message body")
    url, request = calls[0]
    assert url == "https://api.brevo.com/v3/smtp/email"
    assert request["headers"] == {"api-key": "test-key"}
    assert request["json"]["to"] == [{"email": "user@example.com"}]
    assert request["json"]["sender"]["email"] == "alerts@example.com"
