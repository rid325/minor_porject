#!/usr/bin/env python3
"""Upsert the canonical scheme register into MongoDB without deleting records."""

from __future__ import annotations

import argparse
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

from pymongo import UpdateOne
from pymongo.errors import PyMongoError


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.app import config as _config  # noqa: E402,F401
from backend.app.services.auth_service import get_database  # noqa: E402
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
        schemes.create_index("scheme_id", unique=True, name="scheme_id_unique")
        imported_at = datetime.now(timezone.utc)
        operations = []
        for record in seed["schemes"]:
            document = {**record, "updated_at": imported_at}
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
        f"readiness={seed['source']['readiness_counts']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
