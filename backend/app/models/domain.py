"""Small, dependency-light domain objects for the prototype.

The workbook is the source of truth for catalogue records.  The catalogue
objects in this module deliberately do not contain a user's profile; profiles
are evaluated for a request and are never persisted by the API.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from enum import Enum
from typing import Any


class ApplicationReadiness(str, Enum):
    """Research/application-route readiness from the source workbook."""

    YES = "YES"
    CONDITIONAL = "CONDITIONAL"
    NO = "NO"


class RuleReviewState(str, Enum):
    DRAFT = "DRAFT"
    REVIEWED = "REVIEWED"
    UNRESOLVED = "UNRESOLVED"


class RuleStatus(str, Enum):
    PASS = "PASS"
    FAIL = "FAIL"
    UNKNOWN = "UNKNOWN"
    EXTERNAL_CHECK = "EXTERNAL_CHECK"


class EligibilityCategory(str, Enum):
    LIKELY_ELIGIBLE = "likely_eligible"
    NEEDS_MORE_INFORMATION = "needs_more_information"
    LIKELY_NOT_ELIGIBLE = "likely_not_eligible"
    INFORMATION_ONLY = "information_only"


@dataclass(slots=True)
class SourceRecord:
    url: str
    authority: str | None = None
    last_checked: str | None = None
    source_risk: str | None = None
    unresolved_issue: str | None = None
    required_next_action: str | None = None


@dataclass(slots=True)
class SchemeRecord:
    scheme_id: str
    name: str
    jurisdiction: str
    record_type: str | None = None
    category: str | None = None
    discovered_on: str | None = None
    administering_authority: str | None = None
    summary: str | None = None
    eligibility_text: str | None = None
    eligibility_unresolved: str | None = None
    exclusions_text: str | None = None
    documents_required: str | None = None
    conditional_documents: str | None = None
    application_mode: str | None = None
    application_steps: str | None = None
    application_url: str | None = None
    deadline_or_renewal: str | None = None
    tracking_grievance: str | None = None
    source_url: str | None = None
    additional_sources: list[str] = field(default_factory=list)
    source_authority: str | None = None
    extraction_status: str | None = None
    source_risk: str | None = None
    next_review_action: str | None = None
    application_ready: ApplicationReadiness = ApplicationReadiness.NO
    last_checked: str | None = None

    @property
    def sources(self) -> list[SourceRecord]:
        urls: list[str] = []
        for candidate in [self.source_url, *self.additional_sources]:
            if candidate and candidate not in urls:
                urls.append(candidate)
        return [
            SourceRecord(
                url=url,
                authority=self.source_authority,
                last_checked=self.last_checked,
                source_risk=self.source_risk,
                unresolved_issue=self.eligibility_unresolved,
                required_next_action=self.next_review_action,
            )
            for url in urls
        ]

    @property
    def benefit(self) -> str | None:
        """Workbook calls this field ``benefit_summary``; API calls it benefit."""

        return self.summary


@dataclass(slots=True)
class RuleSet:
    scheme_id: str
    version: str
    review_state: RuleReviewState
    expression: dict[str, Any] | None = None
    external_checks: list[str] = field(default_factory=list)
    source_urls: list[str] = field(default_factory=list)
    reviewed_at: str | None = None


@dataclass(slots=True)
class AtomicEvaluation:
    rule_id: str
    status: RuleStatus
    field: str | None = None
    description: str | None = None
    actual_value: Any = None
    expected_value: Any = None
    source_url: str | None = None
    missing_reason: str | None = None
    failure_reason: str | None = None


@dataclass(slots=True)
class EvaluationSummary:
    status: RuleStatus
    conditions: list[AtomicEvaluation] = field(default_factory=list)

    @property
    def passed(self) -> list[AtomicEvaluation]:
        return [item for item in self.conditions if item.status == RuleStatus.PASS]

    @property
    def failed(self) -> list[AtomicEvaluation]:
        return [item for item in self.conditions if item.status == RuleStatus.FAIL]

    @property
    def unknown(self) -> list[AtomicEvaluation]:
        return [item for item in self.conditions if item.status == RuleStatus.UNKNOWN]

    @property
    def external_checks(self) -> list[AtomicEvaluation]:
        return [
            item
            for item in self.conditions
            if item.status == RuleStatus.EXTERNAL_CHECK
        ]


def age_on_date(date_of_birth: date, today: date | None = None) -> int:
    """Return a person's completed years on ``today``."""

    today = today or date.today()
    birthday_has_passed = (today.month, today.day) >= (
        date_of_birth.month,
        date_of_birth.day,
    )
    return today.year - date_of_birth.year - (0 if birthday_has_passed else 1)
