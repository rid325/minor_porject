"""MongoDB-backed email/password accounts and opaque browser sessions."""

from __future__ import annotations

import base64
import hashlib
import hmac
import os
import re
import secrets
from datetime import datetime, timedelta, timezone
from functools import lru_cache
from typing import Any

from bson import ObjectId
from pymongo import MongoClient
from pymongo.errors import DuplicateKeyError, PyMongoError


SESSION_COOKIE_NAME = "yojna_session"
SESSION_TTL = timedelta(days=7)
_EMAIL_PATTERN = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")


class AuthNotConfigured(Exception):
    pass


class EmailAlreadyRegistered(Exception):
    pass


class InvalidCredentials(Exception):
    pass


class InvalidEmail(Exception):
    pass


class WeakPassword(Exception):
    pass


class IncorrectCurrentPassword(Exception):
    pass


def _mongo_uri() -> str:
    uri = os.getenv("MONGODB_URI", "").strip()
    if not uri:
        raise AuthNotConfigured
    return uri


@lru_cache(maxsize=2)
def _client_for(uri: str) -> MongoClient:
    return MongoClient(
        uri,
        appname="YojnaConnect",
        serverSelectionTimeoutMS=5000,
        connectTimeoutMS=5000,
        retryWrites=True,
    )


@lru_cache(maxsize=4)
def _database_for(uri: str, database_name: str):
    database = _client_for(uri)[database_name]
    database.users.create_index("email", unique=True, name="users_email_unique")
    database.sessions.create_index(
        "expires_at", expireAfterSeconds=0, name="sessions_expiry_ttl"
    )
    database.profiles.create_index("user_id", unique=True, name="profiles_user_unique")
    database.saved_documents.create_index([("owner_id", 1), ("created_at", -1), ("_id", -1)])
    return database


def get_database():
    uri = _mongo_uri()
    database_name = os.getenv("MONGODB_DATABASE", "yojna_connect").strip()
    if not database_name:
        database_name = "yojna_connect"
    return _database_for(uri, database_name)


def database_status() -> str:
    if not os.getenv("MONGODB_URI", "").strip():
        return "not_configured"
    try:
        _client_for(_mongo_uri()).admin.command("ping")
    except (PyMongoError, AuthNotConfigured):
        return "unavailable"
    return "connected"


def _normalize_email(email: str) -> str:
    normalized = email.strip().casefold()
    if len(normalized) > 254 or not _EMAIL_PATTERN.fullmatch(normalized):
        raise InvalidEmail
    return normalized


def _hash_password(password: str) -> str:
    if len(password) < 8 or len(password) > 128:
        raise WeakPassword
    salt = secrets.token_bytes(16)
    digest = hashlib.scrypt(
        password.encode("utf-8"), salt=salt, n=2**14, r=8, p=1, dklen=32
    )
    encoded_salt = base64.urlsafe_b64encode(salt).decode("ascii")
    encoded_digest = base64.urlsafe_b64encode(digest).decode("ascii")
    return f"scrypt$16384$8$1${encoded_salt}${encoded_digest}"


def _verify_password(password: str, encoded: str) -> bool:
    try:
        algorithm, n, r, p, salt_text, digest_text = encoded.split("$", 5)
        if algorithm != "scrypt":
            return False
        salt = base64.urlsafe_b64decode(salt_text.encode("ascii"))
        expected = base64.urlsafe_b64decode(digest_text.encode("ascii"))
        actual = hashlib.scrypt(
            password.encode("utf-8"),
            salt=salt,
            n=int(n),
            r=int(r),
            p=int(p),
            dklen=len(expected),
        )
    except (ValueError, TypeError, UnicodeError):
        return False
    return hmac.compare_digest(actual, expected)


def _new_session(database, user_id: ObjectId) -> str:
    token = secrets.token_urlsafe(32)
    token_hash = hashlib.sha256(token.encode("ascii")).hexdigest()
    now = datetime.now(timezone.utc)
    database.sessions.insert_one(
        {
            "token_hash": token_hash,
            "user_id": user_id,
            "created_at": now,
            "expires_at": now + SESSION_TTL,
        }
    )
    return token


def _public_user(document: dict[str, Any]) -> dict[str, Any]:
    return {
        "email": document["email"],
        "created_at": document["created_at"],
    }


def create_account(email: str, password: str) -> tuple[dict[str, Any], str]:
    normalized_email = _normalize_email(email)
    password_hash = _hash_password(password)
    database = get_database()
    now = datetime.now(timezone.utc)
    document = {
        "email": normalized_email,
        "password_hash": password_hash,
        "created_at": now,
    }
    try:
        inserted = database.users.insert_one(document)
    except DuplicateKeyError as exc:
        raise EmailAlreadyRegistered from exc
    user_id = inserted.inserted_id
    user = {**document, "_id": user_id}
    return _public_user(user), _new_session(database, user_id)


def authenticate(email: str, password: str) -> tuple[dict[str, Any], str]:
    normalized_email = _normalize_email(email)
    if not password or len(password) > 128:
        raise InvalidCredentials
    database = get_database()
    user = database.users.find_one({"email": normalized_email})
    if not user or not _verify_password(password, user.get("password_hash", "")):
        raise InvalidCredentials
    return _public_user(user), _new_session(database, user["_id"])


def change_password(user_id: ObjectId, current_password: str, new_password: str) -> None:
    database = get_database()
    user = database.users.find_one({"_id": user_id})
    if not user or not _verify_password(current_password, user.get("password_hash", "")):
        raise IncorrectCurrentPassword
    password_hash = _hash_password(new_password)
    database.users.update_one({"_id": user_id}, {"$set": {"password_hash": password_hash}})


def user_id_for_session(token: str) -> ObjectId | None:
    if not token:
        return None
    token_hash = hashlib.sha256(token.encode("utf-8")).hexdigest()
    database = get_database()
    now = datetime.now(timezone.utc)
    session = database.sessions.find_one(
        {"token_hash": token_hash, "expires_at": {"$gt": now}}
    )
    if not session:
        return None
    if not database.users.find_one({"_id": session["user_id"]}, {"_id": 1}):
        return None
    return session["user_id"]


def user_for_session(token: str) -> dict[str, Any] | None:
    user_id = user_id_for_session(token)
    if user_id is None:
        return None
    database = get_database()
    user = database.users.find_one({"_id": user_id})
    return _public_user(user) if user else None


def revoke_session(token: str) -> None:
    if not token:
        return
    token_hash = hashlib.sha256(token.encode("utf-8")).hexdigest()
    get_database().sessions.delete_one({"token_hash": token_hash})


def cookie_secure() -> bool:
    return os.getenv("AUTH_COOKIE_SECURE", "false").strip().casefold() in {
        "1",
        "true",
        "yes",
        "on",
    }

