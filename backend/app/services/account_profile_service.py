"""Private MongoDB storage for a signed-in applicant's profile answers."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from bson import ObjectId

from .auth_service import get_database
from .condition_normalizer import SCHEMA_VERSION, empty_user_facts, profile_facts_from_profile


def get_profile(user_id: ObjectId) -> dict[str, Any] | None:
    document = get_database().profiles.find_one({"user_id": user_id}, {"_id": 0})
    if not document:
        return None
    user = get_database().users.find_one({"_id": user_id}, {"profile_facts": 1}) or {}
    profile = dict(document.get("profile") or {})
    profile["facts"] = user.get("profile_facts") or {}
    return {"profile": profile, "updated_at": document.get("updated_at")}


def save_profile(user_id: ObjectId, profile: dict[str, Any]) -> dict[str, Any]:
    updated_at = datetime.now(timezone.utc)
    profile_data = dict(profile)
    database = get_database()
    attribute_ids = set(database.condition_attributes.distinct("attribute_id", {"active": True}))
    facts = empty_user_facts(attribute_ids)
    existing = database.users.find_one({"_id": user_id}, {"profile_facts": 1, "legacy_profile_facts": 1}) or {}
    previous_facts = existing.get("profile_facts") or {}
    facts.update({key: value for key, value in previous_facts.items() if key in facts})
    facts.update(profile_facts_from_profile(profile_data, attribute_ids))
    profile_data["facts"] = facts
    user_update = {"$set": {"profile_facts": facts, "profile_schema_version": SCHEMA_VERSION}}
    retired_facts = {key: value for key, value in previous_facts.items() if key not in facts and value is not None}
    if retired_facts:
        user_update["$set"]["legacy_profile_facts"] = {**(existing.get("legacy_profile_facts") or {}), **retired_facts}
    database.users.update_one({"_id": user_id}, user_update)
    database.profiles.update_one(
        {"user_id": user_id},
        {"$set": {"profile": profile_data, "updated_at": updated_at}},
        upsert=True,
    )
    return {"profile": profile_data, "updated_at": updated_at}
