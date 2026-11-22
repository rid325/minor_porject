"""Opt-in alerts for reviewed scheme matches and configured application deadlines."""

from datetime import date, datetime, timedelta, timezone
import json
import os
from urllib.parse import quote

import httpx
from pymongo.errors import DuplicateKeyError

from ..models.domain import EligibilityCategory
from ..schemas.profile import ApplicantProfile
from .auth_service import get_database
from .eligibility_engine import evaluate_scheme
from .scheme_matching import profile_for_scheme

INDIA = timezone(timedelta(hours=5, minutes=30))


class NotificationUnavailable(RuntimeError):
    pass


class ProviderRejected(NotificationUnavailable):
    pass


def setting(name):
    value = os.getenv(name, "").strip()
    if not value:
        raise NotificationUnavailable("The notification provider is not configured.")
    return value


def send_email(recipient, subject, body):
    key = setting("BREVO_API_KEY")
    sender = setting("NOTIFICATION_EMAIL_FROM")
    try:
        response = httpx.post(
            "https://api.brevo.com/v3/smtp/email",
            headers={"api-key": key},
            json={"sender": {"name": "Yojna Connect", "email": sender}, "to": [{"email": recipient}],
                  "subject": subject, "textContent": body},
            timeout=12,
        )
        response.raise_for_status()
    except httpx.HTTPStatusError as exc:
        if exc.response.status_code < 500:
            raise ProviderRejected("Brevo rejected the email request.") from exc
        raise NotificationUnavailable("Brevo did not confirm the email request.") from exc
    except httpx.HTTPError as exc:
        raise NotificationUnavailable("Brevo did not confirm the email request.") from exc


def deadlines_from_config():
    dates = json.loads(os.getenv("SCHEME_NOTIFICATION_DEADLINES", "{}"))
    return {scheme: date.fromisoformat(value) for scheme, value in dates.items()}


def scheme_alerts(scheme, deadline, today):
    if deadline is None or deadline >= today:
        yield "match", "New scheme match", f"{scheme.name} may match your Yojna Connect profile."
    if deadline is not None and 0 <= (deadline - today).days <= 7:
        yield f"deadline:{deadline}", "Application deadline", f"{scheme.name} closes on {deadline:%d %b %Y}."


def matching_alerts(schemes, saved_profile, deadlines, today):
    profile = ApplicantProfile.model_validate(saved_profile).model_dump(mode="python")
    for scheme in schemes:
        category, *_ = evaluate_scheme(scheme, profile_for_scheme(profile, scheme.scheme_id))
        if category != EligibilityCategory.LIKELY_ELIGIBLE:
            continue
        for event, title, summary in scheme_alerts(scheme, deadlines.get(scheme.scheme_id), today):
            yield scheme.scheme_id, event, title, summary


def alert_message(scheme_id, summary, app_url=""):
    path = f"/schemes/{quote(scheme_id, safe='')}"
    return f"Yojna Connect: {summary} Details: {app_url}{path}"


def preview_alerts(repository, saved_profile):
    deadlines = deadlines_from_config()
    today = datetime.now(INDIA).date()
    messages = [
        {"id": f"{scheme}:{event}", "title": title, "text": alert_message(scheme, summary),
         "scheme_path": f"/schemes/{quote(scheme, safe='')}"}
        for scheme, event, title, summary in matching_alerts(repository.all(), saved_profile, deadlines, today)
    ] if saved_profile else []
    return {"has_profile": bool(saved_profile), "has_deadlines": bool(deadlines), "messages": messages}


def dispatch(repository, today=None):
    today = today or datetime.now(INDIA).date()
    deadlines = deadlines_from_config()
    database = get_database()
    schemes = repository.all()
    feature_url = setting("NOTIFICATION_APP_URL").rstrip("/")
    for key in ("BREVO_API_KEY", "NOTIFICATION_EMAIL_FROM"):
        setting(key)
    for preferences in database.notification_preferences.find({"scheme_email_enabled": True}):
        user_id = preferences["_id"]
        user = database.users.find_one({"_id": user_id}, {"email": 1})
        saved = database.profiles.find_one({"user_id": user_id}, {"profile": 1})
        if not user or not saved or not saved.get("profile"):
            continue
        for scheme_id, event, title, summary in matching_alerts(schemes, saved["profile"], deadlines, today):
            body = alert_message(scheme_id, summary, feature_url)
            # Recheck opt-in and the verified number immediately before sending.
            recipient = user.get("email")
            current = database.notification_preferences.find_one({
                "_id": user_id, "scheme_email_enabled": True, "scheme_email_verified": recipient,
            }) if recipient else None
            if not current:
                continue
            delivery_id = f"{user_id}:{scheme_id}:{event}:email"
            outbox = database.notification_deliveries
            try:
                outbox.insert_one({"_id": delivery_id, "status": "sending", "created_at": datetime.now(timezone.utc)})
            except DuplicateKeyError:
                continue
            try:
                send_email(recipient, title, f"{body}\nManage alerts: {feature_url}/account#scheme-alerts")
            except ProviderRejected:
                outbox.delete_one({"_id": delivery_id})
            except NotificationUnavailable:
                outbox.update_one({"_id": delivery_id}, {"$set": {"status": "unconfirmed"}})
            else:
                outbox.update_one({"_id": delivery_id}, {"$set": {"status": "accepted"}})
