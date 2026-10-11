"""Versioned API routes for the scheme prototype."""

from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Any

from fastapi import APIRouter, HTTPException, Query

from ..models.domain import (
    EligibilityCategory,
    RuleReviewState,
    RuleStatus,
    SchemeRecord,
)
from ..schemas.api import (
    EligibilityCheckRequest,
    EligibilityCheckResponse,
    EligibilityConditionResponse,
    EligibilityResultResponse,
    HealthResponse,
    RuleCoverageResponse,
    SchemeDetailResponse,
    SchemeListResponse,
    SchemeSummaryResponse,
    SourceResponse,
)
from ..schemas.profile import ApplicantProfile, ProfileSchemaResponse
from ..services.eligibility_engine import (
    ENGINE_VERSION,
    evaluate_scheme,
    get_rule_set,
)
from ..services.profile_schema_service import get_profile_schema
from ..services.scheme_service import SchemeNotFound, SchemeRepository


router = APIRouter()
repository = SchemeRepository()


DISPLAY_LABELS = {
    EligibilityCategory.LIKELY_ELIGIBLE: "Likely eligible to explore",
    EligibilityCategory.NEEDS_MORE_INFORMATION: "Needs more information",
    EligibilityCategory.LIKELY_NOT_ELIGIBLE: "Likely not eligible",
    EligibilityCategory.INFORMATION_ONLY: "Information only",
}


def _summary(scheme: SchemeRecord) -> SchemeSummaryResponse:
    return SchemeSummaryResponse(
        scheme_id=scheme.scheme_id,
        name=scheme.name,
        jurisdiction=scheme.jurisdiction,
        category=scheme.category,
        benefit=scheme.benefit,
        summary=scheme.summary,
        application_readiness=scheme.application_ready,
        application_url=scheme.application_url,
        last_checked=scheme.last_checked,
        research_status=scheme.extraction_status,
    )


def _rule_count(expression: dict[str, Any] | None) -> int:
    if not expression:
        return 0
    if "all" in expression:
        return sum(_rule_count(child) for child in expression["all"])
    if "any" in expression:
        return sum(_rule_count(child) for child in expression["any"])
    if "not" in expression:
        return _rule_count(expression["not"])
    return 1


def _detail(scheme: SchemeRecord) -> SchemeDetailResponse:
    rule_set = get_rule_set(scheme.scheme_id)
    coverage = RuleCoverageResponse(
        review_state=rule_set.review_state if rule_set else RuleReviewState.UNRESOLVED,
        version=rule_set.version if rule_set else None,
        reviewed_at=rule_set.reviewed_at if rule_set else None,
        evaluated_rule_count=_rule_count(rule_set.expression) if rule_set else 0,
        source_urls=rule_set.source_urls if rule_set else [],
        note=(
            "Reviewed deterministic rules are available for this scheme."
            if rule_set and rule_set.review_state == RuleReviewState.REVIEWED
            else "This record is browseable, but its narrative eligibility criteria are not yet a reviewed machine rule set."
        ),
    )
    return SchemeDetailResponse(
        **_summary(scheme).model_dump(),
        record_type=scheme.record_type,
        administering_authority=scheme.administering_authority,
        eligibility_text=scheme.eligibility_text,
        eligibility_unresolved=scheme.eligibility_unresolved,
        exclusions_text=scheme.exclusions_text,
        documents_required=scheme.documents_required,
        conditional_documents=scheme.conditional_documents,
        application_mode=scheme.application_mode,
        application_steps=scheme.application_steps,
        deadline_or_renewal=scheme.deadline_or_renewal,
        tracking_grievance=scheme.tracking_grievance,
        source_authority=scheme.source_authority,
        source_risk=scheme.source_risk,
        next_review_action=scheme.next_review_action,
        discovered_on=scheme.discovered_on,
        sources=[SourceResponse.model_validate(source) for source in scheme.sources],
        rule_coverage=coverage,
    )


def _serializable(value: Any) -> Any:
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    if isinstance(value, list):
        return [_serializable(item) for item in value]
    if isinstance(value, dict):
        return {key: _serializable(item) for key, item in value.items()}
    return value


def _condition(condition: Any) -> EligibilityConditionResponse:
    return EligibilityConditionResponse(
        rule_id=condition.rule_id,
        status=condition.status,
        field=condition.field,
        description=condition.description,
        actual_value=_serializable(condition.actual_value),
        expected_value=_serializable(condition.expected_value),
        source_url=condition.source_url,
        missing_reason=condition.missing_reason,
        failure_reason=condition.failure_reason,
    )


@router.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse(
        status="ok",
        scheme_count=repository.count,
        data_source=repository.data_source,
        rules_version=ENGINE_VERSION,
        checked_at=datetime.now(timezone.utc),
    )


@router.get("/schemes", response_model=SchemeListResponse)
def list_schemes(
    search: str | None = Query(default=None, description="Search name, benefit or eligibility"),
    jurisdiction: str | None = None,
    category: str | None = None,
    application_ready: str | None = Query(
        default=None,
        description="Filter by workbook readiness: YES, CONDITIONAL, or NO",
    ),
    readiness: str | None = Query(
        default=None,
        description="Alias for application_ready",
        include_in_schema=False,
    ),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=24, ge=1, le=100),
) -> SchemeListResponse:
    records, total = repository.query(
        search=search,
        jurisdiction=jurisdiction,
        category=category,
        application_ready=application_ready or readiness,
        page=page,
        page_size=page_size,
    )
    return SchemeListResponse(
        items=[_summary(scheme) for scheme in records],
        total=total,
        page=page,
        page_size=page_size,
        has_next=page * page_size < total,
    )


@router.get("/schemes/{scheme_id}", response_model=SchemeDetailResponse)
def get_scheme(scheme_id: str) -> SchemeDetailResponse:
    try:
        scheme = repository.get(scheme_id)
    except SchemeNotFound as exc:
        raise HTTPException(status_code=404, detail=f"Scheme {scheme_id!r} was not found") from exc
    return _detail(scheme)


@router.get("/profile/schema", response_model=ProfileSchemaResponse)
def profile_schema() -> ProfileSchemaResponse:
    return get_profile_schema()


@router.post("/eligibility/check", response_model=EligibilityCheckResponse)
def check_eligibility(request: EligibilityCheckRequest) -> EligibilityCheckResponse:
    request_data = request.model_dump(mode="python", exclude_none=False)
    if request.profile is not None:
        profile = request.profile
    else:
        direct_profile = {
            key: value
            for key, value in request_data.items()
            if key not in {"profile", "scheme_ids", "include_information_only"}
        }
        try:
            profile = ApplicantProfile.model_validate(direct_profile)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

    requested_ids = request.scheme_ids
    if requested_ids:
        records = []
        for scheme_id in requested_ids:
            try:
                records.append(repository.get(scheme_id))
            except SchemeNotFound as exc:
                raise HTTPException(
                    status_code=404,
                    detail=f"Scheme {scheme_id!r} was not found",
                ) from exc
    else:
        records = repository.all()

    results: list[EligibilityResultResponse] = []
    for scheme in records:
        category, review_state, rule_set, summary, warnings = evaluate_scheme(scheme, profile)
        if (
            category == EligibilityCategory.INFORMATION_ONLY
            and not request.include_information_only
        ):
            continue
        conditions = [_condition(item) for item in summary.conditions]
        results.append(
            EligibilityResultResponse(
                scheme=_summary(scheme),
                category=category,
                display_label=DISPLAY_LABELS[category],
                rule_set_version=rule_set.version if rule_set else None,
                rule_review_state=review_state,
                passed=[item for item in conditions if item.status == RuleStatus.PASS],
                failed=[item for item in conditions if item.status == RuleStatus.FAIL],
                missing=[item for item in conditions if item.status == RuleStatus.UNKNOWN],
                external_checks=[
                    item for item in conditions if item.status == RuleStatus.EXTERNAL_CHECK
                ],
                warnings=warnings,
                application_url=scheme.application_url,
                application_readiness=scheme.application_ready,
                last_checked=scheme.last_checked,
            )
        )

    counts = {category.value: 0 for category in EligibilityCategory}
    for result in results:
        counts[result.category.value] += 1
    return EligibilityCheckResponse(
        evaluated_at=datetime.now(timezone.utc),
        total_schemes=len(results),
        counts=counts,
        results=results,
    )
