#!/usr/bin/env python3
"""Import the canonical ``Scheme Data`` worksheet into a deterministic JSON seed.

The prototype deliberately keeps this importer dependency-free.  A normal Python
runtime can read the workbook directly from the XLSX zip container, so the seed
can be regenerated in CI or in a minimal backend image without requiring a
spreadsheet package.  The workbook remains the source of truth; this script does
not invent eligibility rules.

Usage from the repository root::

    python3 backend/scripts/import_scheme_workbook.py --check

The default output is ``backend/data/schemes.seed.json``.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import zipfile
from collections import Counter
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Iterable
from xml.etree import ElementTree as ET


SCHEMA_VERSION = "1.0"
SHEET_NAME = "Scheme Data"
EXPECTED_HEADERS = (
    "scheme_id",
    "scheme_name",
    "jurisdiction",
    "record_type",
    "category",
    "discovered_on",
    "administering_body",
    "benefit_summary",
    "eligibility_text",
    "eligibility_unresolved",
    "exclusions_text",
    "documents_required",
    "conditional_documents",
    "application_mode",
    "application_steps",
    "application_url",
    "deadline_or_renewal",
    "tracking_grievance",
    "source_url",
    "additional_sources",
    "source_authority",
    "extraction_status",
    "source_risk",
    "next_review_action",
    "application_ready",
    "last_checked",
)

EXPECTED_READINESS_COUNTS = {"YES": 28, "CONDITIONAL": 24, "NO": 23}
_MAIN_NS = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
_REL_NS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
_PACKAGE_REL_NS = "http://schemas.openxmlformats.org/package/2006/relationships"
_CELL_REF = re.compile(r"^([A-Z]+)([0-9]+)$")


def _local_name(tag: str) -> str:
    """Return the non-namespaced part of an XML tag or attribute name."""

    return tag.rsplit("}", 1)[-1]


def _attribute(element: ET.Element, name: str, default: str | None = None) -> str | None:
    """Read an XML attribute by local name, including namespaced attributes."""

    for key, value in element.attrib.items():
        if _local_name(key).casefold() == name.casefold():
            return value
    return default


def _child(element: ET.Element, name: str) -> ET.Element | None:
    for child in element:
        if _local_name(child.tag) == name:
            return child
    return None


def _text_content(element: ET.Element | None) -> str:
    if element is None:
        return ""
    return "".join(element.itertext())


def _column_index(cell_reference: str) -> int:
    match = _CELL_REF.match(cell_reference)
    if not match:
        raise ValueError(f"Invalid XLSX cell reference: {cell_reference!r}")
    letters = match.group(1)
    index = 0
    for letter in letters:
        index = index * 26 + ord(letter) - ord("A") + 1
    return index - 1


def _read_shared_strings(archive: zipfile.ZipFile) -> list[str]:
    try:
        xml = archive.read("xl/sharedStrings.xml")
    except KeyError:
        return []
    root = ET.fromstring(xml)
    strings: list[str] = []
    for item in root.iter():
        if _local_name(item.tag) != "si":
            continue
        strings.append(_text_content(item))
    return strings


def _worksheet_path(archive: zipfile.ZipFile, sheet_name: str) -> str:
    workbook_root = ET.fromstring(archive.read("xl/workbook.xml"))
    relationships_root = ET.fromstring(archive.read("xl/_rels/workbook.xml.rels"))
    targets = {
        _attribute(rel, "id"): _attribute(rel, "Target")
        for rel in relationships_root
        if _local_name(rel.tag) == "Relationship"
    }
    for sheet in workbook_root.iter():
        if _local_name(sheet.tag) != "sheet":
            continue
        if _attribute(sheet, "name") != sheet_name:
            continue
        relationship_id = _attribute(sheet, "id")
        target = targets.get(relationship_id)
        if not target:
            raise ValueError(f"Worksheet {sheet_name!r} has no relationship target")
        # Targets in this workbook are absolute package paths.  Support relative
        # paths as well, because both forms are valid XLSX relationships.
        return target.lstrip("/") if target.startswith("/") else f"xl/{target}"
    raise ValueError(f"Worksheet {sheet_name!r} was not found")


def _cell_value(cell: ET.Element, shared_strings: list[str]) -> str:
    cell_type = _attribute(cell, "t")
    if cell_type == "inlineStr":
        return _text_content(_child(cell, "is"))
    value_node = _child(cell, "v")
    raw_value = _text_content(value_node)
    if cell_type == "s":
        if not raw_value:
            return ""
        index = int(raw_value)
        try:
            return shared_strings[index]
        except IndexError as exc:
            raise ValueError(f"Shared-string index {index} is out of range") from exc
    if cell_type == "b":
        return "TRUE" if raw_value == "1" else "FALSE"
    # The canonical workbook stores regular text as t="str" and dates as
    # numeric serials.  Keep all non-date values as text so identifiers and
    # source URLs cannot lose leading zeros or punctuation.
    return raw_value


def _read_scheme_rows(workbook_path: Path) -> list[dict[str, str]]:
    with zipfile.ZipFile(workbook_path) as archive:
        worksheet = _worksheet_path(archive, SHEET_NAME)
        root = ET.fromstring(archive.read(worksheet))
        shared_strings = _read_shared_strings(archive)

    rows: dict[int, dict[int, str]] = {}
    for row in root.iter():
        if _local_name(row.tag) != "row":
            continue
        row_number = int(_attribute(row, "r", "0") or "0")
        values: dict[int, str] = {}
        for cell in row:
            if _local_name(cell.tag) != "c":
                continue
            reference = _attribute(cell, "r")
            if not reference:
                continue
            values[_column_index(reference)] = _cell_value(cell, shared_strings)
        rows[row_number] = values

    if not rows:
        raise ValueError(f"Worksheet {SHEET_NAME!r} contains no rows")
    header_row_number = min(rows)
    header_values = rows[header_row_number]
    headers = [header_values.get(index, "") for index in range(max(header_values) + 1)]
    if tuple(headers) != EXPECTED_HEADERS:
        raise ValueError(
            "Unexpected Scheme Data headers. "
            f"Expected {list(EXPECTED_HEADERS)!r}, got {headers!r}"
        )

    parsed: list[dict[str, str]] = []
    for row_number in sorted(rows):
        if row_number == header_row_number:
            continue
        values = rows[row_number]
        if not any(value != "" for value in values.values()):
            continue
        record = {
            header: values.get(index, "")
            for index, header in enumerate(EXPECTED_HEADERS)
        }
        record["_source_row"] = str(row_number)
        parsed.append(record)
    return parsed


def _excel_serial_to_date(value: str) -> str:
    """Convert an Excel 1900-date serial or ISO date to ``YYYY-MM-DD``."""

    text = str(value or "").strip()
    if not text:
        return ""
    if re.fullmatch(r"\d+(?:\.\d+)?", text):
        serial = float(text)
        return (datetime(1899, 12, 30) + timedelta(days=serial)).date().isoformat()
    # Keep a date's calendar value even when the source includes a time.
    match = re.match(r"^(\d{4}-\d{2}-\d{2})", text)
    if match:
        return match.group(1)
    return text


def _normalize_readiness(value: str) -> str:
    normalized = str(value or "").strip().casefold()
    if normalized in {"yes", "y", "true", "ready", "application-ready"}:
        return "YES"
    if "conditional" in normalized:
        return "CONDITIONAL"
    if normalized in {"no", "n", "false", "not ready", "incomplete"}:
        return "NO"
    raise ValueError(f"Unknown application readiness value: {value!r}")


def _split_sources(value: str) -> list[str]:
    return [item.strip() for item in str(value or "").split("|") if item.strip()]


def _normalized_record(raw: dict[str, str]) -> dict[str, Any]:
    record: dict[str, Any] = dict(raw)
    record["last_checked"] = _excel_serial_to_date(raw["last_checked"])
    readiness = _normalize_readiness(raw["application_ready"])
    record["application_readiness"] = readiness
    record["readiness"] = {
        "raw": raw["application_ready"],
        "normalized": readiness,
    }
    record["documents"] = {
        "required": raw["documents_required"],
        "conditional": raw["conditional_documents"],
    }
    record["application_route"] = {
        "mode": raw["application_mode"],
        "url": raw["application_url"],
        "steps": raw["application_steps"],
        "deadline_or_renewal": raw["deadline_or_renewal"],
        "tracking_or_grievance": raw["tracking_grievance"],
    }
    primary_url = raw["source_url"].strip()
    sources: list[dict[str, Any]] = []
    if primary_url:
        sources.append(
            {
                "url": primary_url,
                "role": "primary",
                "authority": raw["source_authority"],
                "source_risk": raw["source_risk"],
                "last_checked": record["last_checked"],
                "unresolved_issue": raw["eligibility_unresolved"],
                "required_next_action": raw["next_review_action"],
            }
        )
    for url in _split_sources(raw["additional_sources"]):
        sources.append(
            {
                "url": url,
                "role": "additional",
                # The workbook stores one review date per scheme rather than a
                # separate date for each URL. Preserve that known date without
                # inventing source-specific review metadata.
                "last_checked": record["last_checked"],
            }
        )
    record["sources"] = sources
    record["unresolved_issues"] = (
        [raw["eligibility_unresolved"]]
        if raw["eligibility_unresolved"].strip()
        else []
    )
    # Keep the source row as an integer for easier diagnostics while leaving the
    # workbook's 26 data columns untouched above.
    record["_source_row"] = int(raw["_source_row"])
    return record


def build_seed(workbook_path: str | Path) -> dict[str, Any]:
    """Read ``Scheme Data`` and return the normalized, JSON-serializable seed."""

    source_path = Path(workbook_path)
    raw_records = _read_scheme_rows(source_path)
    records = [_normalized_record(raw) for raw in raw_records]
    readiness_counts = Counter(record["application_readiness"] for record in records)
    return {
        "schema_version": SCHEMA_VERSION,
        "source": {
            "workbook": source_path.name,
            "worksheet": SHEET_NAME,
            "sha256": hashlib.sha256(source_path.read_bytes()).hexdigest(),
            "headers": list(EXPECTED_HEADERS),
            "record_count": len(records),
            "readiness_counts": {
                status: readiness_counts.get(status, 0)
                for status in ("YES", "CONDITIONAL", "NO")
            },
        },
        "schemes": records,
    }


def validate_seed(
    seed: dict[str, Any],
    *,
    expected_record_count: int | None = None,
    expected_readiness_counts: dict[str, int] | None = None,
) -> None:
    """Raise ``ValueError`` when the seed is incomplete or internally inconsistent."""

    records = seed.get("schemes")
    if not isinstance(records, list):
        raise ValueError("Seed must contain a schemes list")
    ids = [record.get("scheme_id") for record in records]
    if any(not scheme_id for scheme_id in ids):
        raise ValueError("Every scheme must have a non-empty scheme_id")
    duplicates = sorted({scheme_id for scheme_id in ids if ids.count(scheme_id) > 1})
    if duplicates:
        raise ValueError(f"Duplicate scheme IDs: {duplicates}")
    counts = Counter(record.get("application_readiness") for record in records)
    expected_count = expected_record_count if expected_record_count is not None else len(records)
    expected_counts = (
        expected_readiness_counts
        if expected_readiness_counts is not None
        else {status: counts.get(status, 0) for status in ("YES", "CONDITIONAL", "NO")}
    )
    if len(records) != expected_count:
        raise ValueError(f"Expected {expected_count} records, found {len(records)}")
    actual_counts = {status: counts.get(status, 0) for status in ("YES", "CONDITIONAL", "NO")}
    if actual_counts != expected_counts:
        raise ValueError(f"Readiness counts differ: expected {expected_counts}, found {actual_counts}")
    if seed.get("source", {}).get("record_count") != len(records):
        raise ValueError("Source record_count does not match schemes length")
    if seed.get("source", {}).get("readiness_counts") != actual_counts:
        raise ValueError("Source readiness_counts do not match schemes")
    missing = [
        (record.get("scheme_id"), header)
        for record in records
        for header in EXPECTED_HEADERS
        if header not in record
    ]
    if missing:
        raise ValueError(f"Records missing workbook fields: {missing[:5]}")


def write_seed(seed: dict[str, Any], output_path: str | Path) -> None:
    destination = Path(output_path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(
        json.dumps(seed, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def _repository_root() -> Path:
    return Path(__file__).resolve().parents[2]


def main(argv: Iterable[str] | None = None) -> int:
    root = _repository_root()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--workbook",
        type=Path,
        default=root / "outputs" / "scheme_research_register.xlsx",
        help="Canonical workbook containing the Scheme Data worksheet.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=root / "backend" / "data" / "schemes.seed.json",
        help="Destination for the normalized JSON seed.",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Require the canonical 75 records and 28/24/23 readiness counts.",
    )
    args = parser.parse_args(list(argv) if argv is not None else None)
    seed = build_seed(args.workbook)
    validate_seed(
        seed,
        expected_record_count=75 if args.check else None,
        expected_readiness_counts=EXPECTED_READINESS_COUNTS if args.check else None,
    )
    write_seed(seed, args.output)
    print(
        json.dumps(
            {
                "output": str(args.output),
                "record_count": seed["source"]["record_count"],
                "readiness_counts": seed["source"]["readiness_counts"],
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
