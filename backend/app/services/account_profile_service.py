"""Private MongoDB storage for a signed-in applicant's profile answers."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from bson import ObjectId

from .auth_service import get_database


def get_profile(user_id: ObjectId) -> dict[str, Any] | None:
    document = get_database().profiles.find_one({"user_id": user_id}, {"_id": 0})
    if not document:
        return None
    return {"profile": document.get("profile"), "updated_at": document.get("updated_at")}


def save_profile(user_id: ObjectId, profile: dict[str, Any]) -> dict[str, Any]:
    updated_at = datetime.now(timezone.utc)
    profile_data = dict(profile)
    get_database().profiles.update_one(
        {"user_id": user_id},
        {"$set": {"profile": profile_data, "updated_at": updated_at}},
        upsert=True,
    )
    return {"profile": profile_data, "updated_at": updated_at}
