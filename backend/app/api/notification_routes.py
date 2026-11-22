"""Account-scoped verification and opt-in for scheme alerts."""

from datetime import datetime, timedelta, timezone
from hmac import compare_digest, digest
from secrets import randbelow, token_hex

from fastapi import APIRouter, HTTPException, Request, Response
from pydantic import BaseModel, Field
from pymongo.errors import DuplicateKeyError, PyMongoError

from .auth_routes import _require_user_id
from .routes import repository
from ..services import account_profile_service, auth_service, scheme_notifications as alerts

router = APIRouter(prefix="/notifications", tags=["notifications"])


class VerificationCode(BaseModel):
    code: str = Field(pattern=r"^[0-9]{6}$")


class Preferences(BaseModel):
    email_enabled: bool


def account(request, response):
    response.headers["Cache-Control"] = "no-store"
    user_id = _require_user_id(request)
    database = auth_service.get_database()
    user = database.users.find_one({"_id": user_id}, {"email": 1})
    if not user:
        raise HTTPException(status_code=401, detail="Sign in again to manage alerts.")
    return database.notification_preferences, user_id, user["email"]


def public_settings(record, email):
    verified = record.get("scheme_email_verified") == email
    return {
        "email": email, "email_verified": verified,
        "email_enabled": verified and bool(record.get("scheme_email_enabled")),
    }


def code_digest(user_id, nonce, code):
    key = alerts.setting("BREVO_API_KEY").encode()
    return digest(key, f"scheme-email:{user_id}:{nonce}:{code}".encode(), "sha256").hex()


@router.get("/demo")
def demo_inbox(request: Request, response: Response):
    response.headers["Cache-Control"] = "no-store"
    user_id = _require_user_id(request)
    try:
        saved = account_profile_service.get_profile(user_id) or {}
        return alerts.preview_alerts(repository, saved.get("profile"))
    except (ValueError, TypeError, auth_service.AuthNotConfigured, PyMongoError) as exc:
        raise HTTPException(status_code=503, detail="The demo inbox is temporarily unavailable.") from exc


@router.get("")
def get_settings(request: Request, response: Response):
    try:
        collection, user_id, email = account(request, response)
        return public_settings(collection.find_one({"_id": user_id}) or {}, email)
    except (auth_service.AuthNotConfigured, PyMongoError) as exc:
        raise HTTPException(status_code=503, detail="Alert settings are unavailable.") from exc


@router.put("")
def update_settings(body: Preferences, request: Request, response: Response):
    try:
        collection, user_id, email = account(request, response)
        query = {"_id": user_id}
        if body.email_enabled:
            query["scheme_email_verified"] = email
        record = collection.find_one_and_update(query, {"$set": {"scheme_email_enabled": body.email_enabled}}, return_document=True)
        if record is None and body.email_enabled:
            raise HTTPException(status_code=422, detail="Verify your registered email before turning on alerts.")
        return public_settings(record or {}, email)
    except (auth_service.AuthNotConfigured, PyMongoError) as exc:
        raise HTTPException(status_code=503, detail="Alert settings are unavailable.") from exc


@router.post("/verify/email")
def start_verification(request: Request, response: Response):
    try:
        collection, user_id, email = account(request, response)
        now = datetime.now(timezone.utc)
        last = "scheme_email_last_code"
        code = f"{randbelow(1_000_000):06d}"
        nonce = token_hex(16)
        pending = {"nonce": nonce, "digest": code_digest(user_id, nonce, code), "destination": email,
                   "expires_at": now + timedelta(minutes=10), "attempts": 0}
        collection.update_one(
            {"_id": user_id, "$or": [{last: {"$lt": now - timedelta(minutes=1)}}, {last: {"$exists": False}}]},
            {"$set": {last: now, "scheme_email_pending": pending}}, upsert=True,
        )
        alerts.send_email(email, "Verify your Yojna Connect email", f"Your verification code is {code}. It expires in 10 minutes.")
        return {"sent": True}
    except DuplicateKeyError as exc:
        raise HTTPException(status_code=429, detail="Wait one minute before requesting another code.") from exc
    except (alerts.NotificationUnavailable, auth_service.AuthNotConfigured, PyMongoError, KeyError) as exc:
        raise HTTPException(status_code=503, detail="The verification code could not be sent.") from exc


@router.post("/verify/email/confirm")
def confirm_verification(body: VerificationCode, request: Request, response: Response):
    try:
        collection, user_id, email = account(request, response)
        key = "scheme_email_pending"
        query = {"_id": user_id, f"{key}.expires_at": {"$gt": datetime.now(timezone.utc)}, f"{key}.destination": email}
        record = collection.find_one_and_update(
            {**query, f"{key}.attempts": {"$lt": 5}}, {"$inc": {f"{key}.attempts": 1}},
        )
        if not record:
            raise HTTPException(status_code=422, detail="Request a new verification code.")
        pending = record[key]
        if not compare_digest(pending["digest"], code_digest(user_id, pending["nonce"], body.code)):
            raise HTTPException(status_code=422, detail="The verification code was not accepted.")
        updated = collection.find_one_and_update(
            {**query, f"{key}.nonce": pending["nonce"]},
            {"$set": {"scheme_email_verified": email}, "$unset": {key: ""}},
            return_document=True,
        )
        if updated is None:
            raise HTTPException(status_code=422, detail="Request a new verification code.")
        return public_settings(updated, email)
    except (alerts.NotificationUnavailable, auth_service.AuthNotConfigured, PyMongoError) as exc:
        raise HTTPException(status_code=503, detail="Verification is unavailable.") from exc
