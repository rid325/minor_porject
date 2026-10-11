"""Workbook-backed scheme catalogue service.

The prototype intentionally uses an in-memory repository.  It keeps the API
usable without PostgreSQL while retaining a clean seam for a later SQL-backed
repository.  The XLSX reader below only uses the Python standard library, so
the catalogue can boot as soon as the FastAPI requirements are installed.
"""

from __future__ import annotations

import os
import json
import posixpath
import re
import zipfile
from pathlib import Path
from typing import Iterable
from xml.etree import ElementTree as ET

from ..models.domain import ApplicationReadiness, SchemeRecord


MAIN_NS = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
REL_NS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
PKG_REL_NS = "http://schemas.openxmlformats.org/package/2006/relationships"
NS = "{" + MAIN_NS + "}"


class SchemeNotFound(KeyError):
    """Raised when a requested scheme id is not in the catalogue."""


def _column_number(cell_reference: str) -> int:
    letters = re.match(r"[A-Za-z]+", cell_reference)
    if not letters:
        return 0
    number = 0
    for letter in letters.group(0).upper():
        number = number * 26 + (ord(letter) - ord("A") + 1)
    return number


def _join_inline_text(node: ET.Element) -> str:
    return "".join(text or "" for text in node.iter(NS + "t"))


def _read_xlsx_sheet(path: Path, wanted_sheet: str) -> list[dict[str, str]]:
    """Read one simple XLSX worksheet into dictionaries keyed by headers."""

    with zipfile.ZipFile(path) as workbook:
        names = set(workbook.namelist())
        shared_strings: list[str] = []
        if "xl/sharedStrings.xml" in names:
            strings_root = ET.fromstring(workbook.read("xl/sharedStrings.xml"))
            for string_item in strings_root.findall(NS + "si"):
                shared_strings.append(_join_inline_text(string_item))

        workbook_root = ET.fromstring(workbook.read("xl/workbook.xml"))
        rels_root = ET.fromstring(workbook.read("xl/_rels/workbook.xml.rels"))
        relationships = {
            item.attrib["Id"]: item.attrib["Target"]
            for item in rels_root.findall("{" + PKG_REL_NS + "}Relationship")
        }
        target: str | None = None
        for sheet in workbook_root.findall(".//" + NS + "sheet"):
            if sheet.attrib.get("name") != wanted_sheet:
                continue
            relationship_id = sheet.attrib.get("{" + REL_NS + "}id")
            if relationship_id:
                target = relationships.get(relationship_id)
            break
        if not target:
            raise FileNotFoundError(f"Worksheet {wanted_sheet!r} not found")

        target = posixpath.normpath(target.lstrip("/"))
        if not target.startswith("xl/"):
            target = posixpath.normpath(posixpath.join("xl", target))
        sheet_root = ET.fromstring(workbook.read(target))

        raw_rows: list[dict[int, str]] = []
        for row in sheet_root.findall(".//" + NS + "sheetData/" + NS + "row"):
            values: dict[int, str] = {}
            for cell in row.findall(NS + "c"):
                column = _column_number(cell.attrib.get("r", ""))
                if not column:
                    continue
                cell_type = cell.attrib.get("t")
                if cell_type == "inlineStr":
                    value = _join_inline_text(cell.find(NS + "is") or cell)
                else:
                    value_node = cell.find(NS + "v")
                    value = value_node.text if value_node is not None else ""
                    if cell_type == "s" and value:
                        try:
                            value = shared_strings[int(value)]
                        except (IndexError, ValueError):
                            value = ""
                    elif cell_type == "b":
                        value = "TRUE" if value == "1" else "FALSE"
                values[column] = value
            raw_rows.append(values)

    if not raw_rows:
        return []
    headers = {
        number: value.strip()
        for number, value in raw_rows[0].items()
        if value and value.strip()
    }
    rows: list[dict[str, str]] = []
    for raw in raw_rows[1:]:
        record = {
            header: (raw.get(number, "") or "").strip()
            for number, header in headers.items()
        }
        if record.get("scheme_id"):
            rows.append(record)
    return rows


def _clean(value: str | None) -> str | None:
    if value is None:
        return None
    cleaned = value.strip()
    return cleaned or None


def _split_urls(value: str | None) -> list[str]:
    cleaned = _clean(value)
    if not cleaned:
        return []
    return [item.strip() for item in re.split(r"\s*\|\s*", cleaned) if item.strip()]


def _readiness(value: str | None) -> ApplicationReadiness:
    normalized = (_clean(value) or "NO").upper()
    if normalized == "YES":
        return ApplicationReadiness.YES
    if normalized == "CONDITIONAL":
        return ApplicationReadiness.CONDITIONAL
    return ApplicationReadiness.NO


def row_to_scheme(row: dict[str, str]) -> SchemeRecord:
    """Map the canonical ``Scheme Data`` row to the API domain object."""

    return SchemeRecord(
        scheme_id=row.get("scheme_id", "").strip(),
        name=row.get("scheme_name", "").strip(),
        jurisdiction=row.get("jurisdiction", "").strip(),
        record_type=_clean(row.get("record_type")),
        category=_clean(row.get("category")),
        discovered_on=_clean(row.get("discovered_on")),
        administering_authority=_clean(row.get("administering_body")),
        summary=_clean(row.get("benefit_summary")),
        eligibility_text=_clean(row.get("eligibility_text")),
        eligibility_unresolved=_clean(row.get("eligibility_unresolved")),
        exclusions_text=_clean(row.get("exclusions_text")),
        documents_required=_clean(row.get("documents_required")),
        conditional_documents=_clean(row.get("conditional_documents")),
        application_mode=_clean(row.get("application_mode")),
        application_steps=_clean(row.get("application_steps")),
        application_url=_clean(row.get("application_url")),
        deadline_or_renewal=_clean(row.get("deadline_or_renewal")),
        tracking_grievance=_clean(row.get("tracking_grievance")),
        source_url=_clean(row.get("source_url")),
        additional_sources=_split_urls(row.get("additional_sources")),
        source_authority=_clean(row.get("source_authority")),
        extraction_status=_clean(row.get("extraction_status")),
        source_risk=_clean(row.get("source_risk")),
        next_review_action=_clean(row.get("next_review_action")),
        application_ready=_readiness(row.get("application_ready")),
        last_checked=_clean(row.get("last_checked")),
    )


def default_workbook_path() -> Path:
    configured = os.getenv("SCHEME_WORKBOOK_PATH")
    if configured:
        return Path(configured).expanduser()
    # .../repo/backend/app/services/scheme_service.py -> repo
    return Path(__file__).resolve().parents[3] / "outputs" / "scheme_research_register.xlsx"


def default_seed_path() -> Path:
    return Path(__file__).resolve().parents[2] / "data" / "schemes.seed.json"


class SchemeRepository:
    """In-memory query service for the 75-row scheme catalogue."""

    def __init__(self, workbook_path: Path | None = None):
        self.workbook_path = workbook_path or default_workbook_path()
        self.seed_path = default_seed_path()
        self.data_source = "workbook"
        self._schemes: dict[str, SchemeRecord] = {}
        self.reload()

    def reload(self) -> None:
        try:
            rows = _read_xlsx_sheet(self.workbook_path, "Scheme Data")
        except (FileNotFoundError, OSError, zipfile.BadZipFile):
            # Prefer the checked-in, importer-produced JSON seed when the
            # source workbook is not mounted. It preserves every workbook
            # column and keeps the API runnable in a minimal deployment.
            try:
                seed = json.loads(self.seed_path.read_text(encoding="utf-8"))
                rows = [
                    {
                        key: str(value) if value is not None else ""
                        for key, value in record.items()
                        if not key.startswith("_")
                    }
                    for record in seed.get("schemes", [])
                    if record.get("scheme_id")
                ]
            except (OSError, ValueError, TypeError):
                # Keep health/catalogue routes bootable if an operator starts
                # the API before mounting either catalogue artifact.
                rows = []
                self.data_source = "empty-fallback"
            else:
                self.data_source = f"seed:{self.seed_path.name}"
        else:
            self.data_source = f"workbook:{self.workbook_path.name}"
        self._schemes = {
            scheme.scheme_id: scheme
            for row in rows
            if (scheme := row_to_scheme(row)).scheme_id
        }

    @property
    def count(self) -> int:
        return len(self._schemes)

    def all(self) -> list[SchemeRecord]:
        return sorted(self._schemes.values(), key=lambda scheme: scheme.name.casefold())

    def get(self, scheme_id: str) -> SchemeRecord:
        try:
            return self._schemes[scheme_id]
        except KeyError as exc:
            raise SchemeNotFound(scheme_id) from exc

    def query(
        self,
        *,
        search: str | None = None,
        jurisdiction: str | None = None,
        category: str | None = None,
        application_ready: str | None = None,
        page: int = 1,
        page_size: int = 24,
    ) -> tuple[list[SchemeRecord], int]:
        records: Iterable[SchemeRecord] = self.all()
        if search:
            needle = search.casefold().strip()
            records = [
                scheme
                for scheme in records
                if needle in scheme.name.casefold()
                or needle in (scheme.summary or "").casefold()
                or needle in (scheme.eligibility_text or "").casefold()
            ]
        if jurisdiction:
            needle = jurisdiction.casefold().strip()
            records = [
                scheme
                for scheme in records
                if needle in scheme.jurisdiction.casefold()
            ]
        if category:
            needle = category.casefold().strip()
            records = [
                scheme
                for scheme in records
                if needle in (scheme.category or "").casefold()
            ]
        if application_ready:
            desired = _readiness(application_ready)
            records = [scheme for scheme in records if scheme.application_ready == desired]
        materialized = list(records)
        total = len(materialized)
        start = max(page - 1, 0) * page_size
        return materialized[start : start + page_size], total
