#!/usr/bin/env python3
"""Upsert the canonical scheme register into MongoDB without deleting records."""

from __future__ import annotations

import argparse
import os
import sys
from datetime import datetime, timezone
from dataclasses import asdict
from pathlib import Path

from pymongo import UpdateOne
from pymongo.errors import PyMongoError


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.app import config as _config  # noqa: E402,F401
from backend.app.services.auth_service import get_database  # noqa: E402
from backend.app.services.condition_normalizer import (  # noqa: E402
    SCHEMA_VERSION, build_catalog, empty_user_facts, profile_facts_from_profile,
)
from backend.app.services.eligibility_engine import RULE_SETS  # noqa: E402
from backend.scripts.import_scheme_workbook import (  # noqa: E402
    EXPECTED_READINESS_COUNTS,
    build_seed,
    validate_seed,
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--workbook",
        type=Path,
        default=Path(
            os.getenv(
                "SCHEME_WORKBOOK_PATH",
                str(ROOT / "outputs" / "scheme_research_register.xlsx"),
            )
        ),
        help="Workbook containing the canonical Scheme Data worksheet.",
    )
    args = parser.parse_args()

    seed = build_seed(args.workbook)
    validate_seed(
        seed,
        expected_record_count=75,
        expected_readiness_counts=EXPECTED_READINESS_COUNTS,
    )

    try:
        database = get_database()
        schemes = database.schemes
        database.condition_attributes.create_index("attribute_id", unique=True, name="condition_attribute_id_unique")
        database.scheme_rules.create_index("scheme_id", unique=True, name="scheme_rules_id_unique")
        schemes.create_index("scheme_id", unique=True, name="scheme_id_unique")
        imported_at = datetime.now(timezone.utc)
        reviewed = {scheme_id: asdict(rule) for scheme_id, rule in RULE_SETS.items()}
        normalized_schemes, attributes = build_catalog(seed["schemes"], reviewed)
        normalized_by_id = {item["scheme_id"]: item for item in normalized_schemes}
        operations = []
        for record in seed["schemes"]:
            normalized = normalized_by_id[record["scheme_id"]]
            document = {**record, "normalized_conditions": normalized["normalized_conditions"], "condition_schema_version": SCHEMA_VERSION, "condition_review_state": normalized["review_state"], "updated_at": imported_at}
            operations.append(
                UpdateOne(
                    {"scheme_id": record["scheme_id"]},
                    {
                        "$set": document,
                        "$setOnInsert": {"created_at": imported_at},
                    },
                    upsert=True,
                )
            )
        result = schemes.bulk_write(operations, ordered=False)
        database.condition_attributes.update_many({}, {"$set": {"active": False}})
        database.condition_attributes.bulk_write([
            UpdateOne({"attribute_id": attribute["attribute_id"]}, {"$set": {**attribute, "active": True, "updated_at": imported_at}, "$setOnInsert": {"created_at": imported_at}}, upsert=True)
            for attribute in attributes
        ], ordered=False)
        database.scheme_rules.bulk_write([
            UpdateOne({"scheme_id": item["scheme_id"]}, {"$set": {**item, "updated_at": imported_at}, "$setOnInsert": {"created_at": imported_at}}, upsert=True)
            for item in normalized_schemes
        ], ordered=False)
        migrated_users = 0
        for user in database.users.find({}, {"_id": 1, "profile_facts": 1, "legacy_profile_facts": 1}):
            old = database.profiles.find_one({"user_id": user["_id"]}, {"profile": 1}) or {}
            facts = empty_user_facts({attribute["attribute_id"] for attribute in attributes})
            facts.update(profile_facts_from_profile(old.get("profile") or {}, set(facts)))
            previous_facts = user.get("profile_facts") or {}
            facts.update({key: value for key, value in previous_facts.items() if key in facts and value is not None})
            retired_facts = {key: value for key, value in previous_facts.items() if key not in facts and value is not None}
            update = {"$set": {"profile_facts": facts, "profile_schema_version": SCHEMA_VERSION}}
            if retired_facts:
                update["$set"]["legacy_profile_facts"] = {**(user.get("legacy_profile_facts") or {}), **retired_facts}
            database.users.update_one({"_id": user["_id"]}, update)
            migrated_users += 1
        database.register_metadata.update_one(
            {"_id": "scheme_research_register"},
            {
                "$set": {
                    "workbook": args.workbook.name,
                    "worksheet": seed["source"]["worksheet"],
                    "source_sha256": seed["source"]["sha256"],
                    "record_count": seed["source"]["record_count"],
                    "readiness_counts": seed["source"]["readiness_counts"],
                    "supporting_sheet_counts": seed["source"]["supporting_sheet_counts"],
                    "category_coverage": seed["source"]["category_coverage"],
                    "field_guide": seed["source"]["field_guide"],
                    "imported_at": imported_at,
                }
            },
            upsert=True,
        )
    except PyMongoError as exc:
        # Keep connection strings and server details out of terminal logs.
        print(f"MongoDB import failed ({type(exc).__name__}). Check Atlas credentials and Network Access.")
        return 2

    print(
        "Imported scheme register: "
        f"75 records; inserted={result.upserted_count}, updated={result.modified_count}; "
        f"readiness={seed['source']['readiness_counts']}; normalized_conditions={sum(len(item['normalized_conditions']) for item in normalized_schemes)}; user_profiles_migrated={migrated_users}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
