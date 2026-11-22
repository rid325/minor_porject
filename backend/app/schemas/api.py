"""Public HTTP request and response contracts."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from ..models.domain import (
    ApplicationReadiness,
    EligibilityCategory,
    RuleReviewState,
    RuleStatus,
)
from .profile import ApplicantProfile


class SourceResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    url: str
    authority: str | None = None
    last_checked: str | None = None
    source_risk: str | None = None
    unresolved_issue: str | None = None
    required_next_action: str | None = None


class RuleCoverageResponse(BaseModel):
    review_state: RuleReviewState
    version: str | None = None
    reviewed_at: str | None = None
    evaluated_rule_count: int = 0
    source_urls: list[str] = Field(default_factory=list)
    note: str | None = None


class SchemeSummaryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    scheme_id: str
    name: str
    jurisdiction: str
    category: str | None = None
    benefit: str | None = None
    summary: str | None = None
    application_readiness: ApplicationReadiness
    application_url: str | None = None
    last_checked: str | None = None
    research_status: str | None = None


class ApplicationGuideResponse(BaseModel):
    who_should_try: str | None = None
    benefit: str | None = None
    documents_to_prepare: str | None = None
    where_to_apply: str | None = None
    application_walkthrough: str | None = None
    timing_and_tracking: str | None = None
    important_caution: str | None = None


class SchemeDetailResponse(SchemeSummaryResponse):
    record_type: str | None = None
    administering_authority: str | None = None
    eligibility_text: str | None = None
    eligibility_unresolved: str | None = None
    exclusions_text: str | None = None
    documents_required: str | None = None
    conditional_documents: str | None = None
    application_mode: str | None = None
    application_steps: str | None = None
    deadline_or_renewal: str | None = None
    tracking_grievance: str | None = None
    source_authority: str | None = None
    source_risk: str | None = None
    next_review_action: str | None = None
    discovered_on: str | None = None
    application_guide: ApplicationGuideResponse | None = None
    sources: list[SourceResponse] = Field(default_factory=list)
    rule_coverage: RuleCoverageResponse


class SchemeListResponse(BaseModel):
    items: list[SchemeSummaryResponse]
    total: int
    page: int
    page_size: int
    has_next: bool


class EligibilityConditionResponse(BaseModel):
    rule_id: str
    status: RuleStatus
    field: str | None = None
    description: str | None = None
    actual_value: Any = None
    expected_value: Any = None
    source_url: str | None = None
    missing_reason: str | None = None
    failure_reason: str | None = None


class EligibilityResultResponse(BaseModel):
    scheme: SchemeSummaryResponse
    category: EligibilityCategory
    display_label: str
    rule_set_version: str | None = None
    rule_review_state: RuleReviewState
    passed: list[EligibilityConditionResponse] = Field(default_factory=list)
    failed: list[EligibilityConditionResponse] = Field(default_factory=list)
    missing: list[EligibilityConditionResponse] = Field(default_factory=list)
    external_checks: list[EligibilityConditionResponse] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    application_url: str | None = None
    application_readiness: ApplicationReadiness
    last_checked: str | None = None


class EligibilityCheckRequest(BaseModel):
    """Request body.

    ``profile`` is the preferred shape.  The endpoint also accepts the
    profile sections directly at the top level for a forgiving first-party
    integration, while still validating them through ``ApplicantProfile``.
    """

    model_config = ConfigDict(extra="allow")

    profile: ApplicantProfile | None = None
    scheme_ids: list[str] | None = None
    include_information_only: bool = True


class EligibilityCheckResponse(BaseModel):
    evaluated_at: datetime
    profile_schema_version: str = "1.0"
    rule_engine_version: str = "1.0"
    total_schemes: int
    counts: dict[str, int]
    results: list[EligibilityResultResponse]
    disclaimer: str = (
        "This is a pre-screening result, not an approval or guarantee. "
        "The department, bank, or scheme authority makes the final decision."
    )


class HealthResponse(BaseModel):
    status: str
    scheme_count: int
    data_source: str
    rules_version: str
    checked_at: datetime
    database_status: str = "not_configured"


class AuthCredentialsRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    email: str = Field(min_length=3, max_length=254)
    password: str = Field(min_length=8, max_length=128)


class AuthUserResponse(BaseModel):
    email: str
    created_at: datetime


class AuthStatusResponse(BaseModel):
    authenticated: bool
    user: AuthUserResponse | None = None


class AccountProfileResponse(BaseModel):
    profile: dict[str, Any] | None = None
    updated_at: datetime | None = None


class AccountProfileSaveRequest(BaseModel):
    profile: dict[str, Any]


class ChangePasswordRequest(BaseModel):
    current_password: str = Field(min_length=1, max_length=128)
    new_password: str = Field(min_length=8, max_length=128)
