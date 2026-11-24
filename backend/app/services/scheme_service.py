"""Workbook-backed scheme catalogue service.

The prototype intentionally uses an in-memory repository.  It keeps the API
usable without PostgreSQL while retaining a clean seam for a later SQL-backed
repository.  The XLSX reader below only uses the Python standard library, so
the catalogue can boot as soon as the FastAPI requirements are installed.
"""

from __future__ import annotations

import os
import json
import re
import zipfile
from pathlib import Path
from typing import Iterable

from pymongo.errors import PyMongoError

from ..models.domain import ApplicationReadiness, SchemeRecord


class SchemeNotFound(KeyError):
    """Raised when a requested scheme id is not in the catalogue."""


def _clean(value: str | None) -> str | None:
    if value is None:
        return None
    cleaned = value.strip()
    return cleaned or None


def _split_urls(value: str | None) -> list[str]:
    cleaned = _clean(value)
    if not cleaned:
        return []
    return [item.strip() for item in re.split(r"\s*[|;]\s*(?=https?://)", cleaned) if item.strip()]


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
        application_guide=row.get("application_guide") or None,
        ready_to_apply_snapshot=row.get("ready_to_apply_snapshot") or None,
        resolution_snapshot=row.get("resolution_snapshot") or None,
        normalized_conditions=row.get("normalized_conditions") or [],
        condition_schema_version=_clean(row.get("condition_schema_version")),
        condition_review_state=_clean(row.get("condition_review_state")),
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
            from .auth_service import AuthNotConfigured, get_database

            database = get_database()
            mongo_rows = list(database.schemes.find({}, {"_id": 0}))
        except (AuthNotConfigured, PyMongoError):
            mongo_rows = []
            database = None
        if mongo_rows:
            def preserve_nested(value):
                if isinstance(value, dict):
                    return {key: preserve_nested(item) for key, item in value.items()}
                if isinstance(value, list):
                    return [preserve_nested(item) for item in value]
                if hasattr(value, "isoformat"):
                    return value.isoformat()
                return str(value) if value is not None else ""

            rows = [
                {
                    key: preserve_nested(value)
                    for key, value in record.items()
                }
                for record in mongo_rows
            ]
            self.data_source = f"mongodb:{database.name}.schemes"
            self._schemes = {
                scheme.scheme_id: scheme
                for row in rows
                if (scheme := row_to_scheme(row)).scheme_id
            }
            return

        try:
            if __package__.startswith("backend."):
                from backend.scripts.import_scheme_workbook import build_seed
            else:
                from scripts.import_scheme_workbook import build_seed
            rows = build_seed(self.workbook_path)["schemes"]
        except (FileNotFoundError, OSError, zipfile.BadZipFile):
            # Prefer the checked-in, importer-produced JSON seed when the
            # source workbook is not mounted. It preserves every workbook
            # column and keeps the API runnable in a minimal deployment.
            try:
                seed = json.loads(self.seed_path.read_text(encoding="utf-8"))
                rows = [
                    {
                        key: value if isinstance(value, (dict, list)) else str(value) if value is not None else ""
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

