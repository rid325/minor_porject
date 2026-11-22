from __future__ import annotations

import copy
import json
import re
import tempfile
import unittest
from pathlib import Path

from backend.scripts.import_scheme_workbook import (
    EXPECTED_HEADERS,
    EXPECTED_READINESS_COUNTS,
    build_seed,
    validate_seed,
    write_seed,
)


ROOT = Path(__file__).resolve().parents[2]
WORKBOOK = ROOT / "outputs" / "scheme_research_register.xlsx"
SEED_PATH = ROOT / "backend" / "data" / "schemes.seed.json"


class SchemeImportTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.seed = build_seed(WORKBOOK)
        cls.records = cls.seed["schemes"]

    def test_canonical_record_and_readiness_counts(self) -> None:
        self.assertEqual(len(self.records), 75)
        self.assertEqual(
            self.seed["source"]["readiness_counts"], EXPECTED_READINESS_COUNTS
        )
        self.assertEqual(
            {record["application_readiness"] for record in self.records},
            {"YES", "CONDITIONAL", "NO"},
        )
        validate_seed(
            self.seed,
            expected_record_count=75,
            expected_readiness_counts=EXPECTED_READINESS_COUNTS,
        )

    def test_scheme_ids_are_unique_and_all_workbook_fields_survive(self) -> None:
        ids = [record["scheme_id"] for record in self.records]
        self.assertEqual(len(ids), len(set(ids)))
        for record in self.records:
            self.assertTrue(set(EXPECTED_HEADERS).issubset(record))
            self.assertTrue(record["scheme_id"])
            self.assertTrue(record["scheme_name"])

    def test_documents_application_route_sources_and_unresolved_fields_are_normalized(self) -> None:
        record = next(item for item in self.records if item["scheme_id"] == "HR-MSYBC")
        self.assertEqual(record["application_ready"], "Conditional")
        self.assertEqual(record["application_readiness"], "CONDITIONAL")
        self.assertEqual(record["documents"]["required"], record["documents_required"])
        self.assertEqual(
            record["documents"]["conditional"], record["conditional_documents"]
        )
        self.assertEqual(record["application_route"]["mode"], record["application_mode"])
        self.assertEqual(record["application_route"]["url"], record["application_url"])
        self.assertEqual(record["application_route"]["steps"], record["application_steps"])
        self.assertEqual(
            record["application_route"]["tracking_or_grievance"],
            record["tracking_grievance"],
        )
        self.assertEqual(record["sources"][0]["url"], record["source_url"])
        self.assertEqual(record["sources"][0]["role"], "primary")
        self.assertEqual(record["sources"][0]["last_checked"], record["last_checked"])
        self.assertEqual(record["sources"][0]["source_risk"], record["source_risk"])
        self.assertEqual(
            record["sources"][0]["unresolved_issue"],
            record["eligibility_unresolved"],
        )
        self.assertEqual(
            record["sources"][0]["required_next_action"],
            record["next_review_action"],
        )
        self.assertTrue(
            all(source["last_checked"] == record["last_checked"] for source in record["sources"])
        )
        self.assertEqual(record["unresolved_issues"], [record["eligibility_unresolved"]])
        self.assertRegex(record["last_checked"], re.compile(r"^\d{4}-\d{2}-\d{2}$"))

    def test_import_is_repeatable_and_matches_committed_seed(self) -> None:
        second_seed = build_seed(WORKBOOK)
        self.assertEqual(self.seed, second_seed)
        committed = json.loads(SEED_PATH.read_text(encoding="utf-8"))
        self.assertEqual(self.seed, committed)
        with tempfile.TemporaryDirectory() as temporary_directory:
            output = Path(temporary_directory) / "schemes.seed.json"
            write_seed(self.seed, output)
            self.assertEqual(output.read_bytes(), SEED_PATH.read_bytes())

    def test_validation_rejects_duplicate_ids(self) -> None:
        invalid_seed = copy.deepcopy(self.seed)
        invalid_seed["schemes"].append(copy.deepcopy(invalid_seed["schemes"][0]))
        invalid_seed["source"]["record_count"] += 1
        with self.assertRaisesRegex(ValueError, "Duplicate scheme IDs"):
            validate_seed(invalid_seed)


if __name__ == "__main__":
    unittest.main()
