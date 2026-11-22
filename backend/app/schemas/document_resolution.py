"""Validated request and model decision for document correction guides."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from .document_checks import FieldName, ShortText


class ComparedDocument(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: str = Field(pattern=r"^[a-z0-9_]{1,40}$")
    value: ShortText
    ocr_confidence: float | None = Field(default=None, ge=0, le=1)


class ResolutionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    documents: tuple[ComparedDocument, ComparedDocument]
    field: FieldName
    verified_record: Literal["unknown", "first", "second", "neither"] = "unknown"
    ai_consent: bool = False
    share_conflicting_values: bool = False


class GuideDecision(BaseModel):
    model_config = ConfigDict(extra="forbid")

    emphasis: Literal["application", "evidence", "ocr"]
    follow_up: Literal["confirm_record", "uidai_history", "registration_area", "issuer_process"]


class GeminiGuideDecision(GuideDecision):
    possible_reason: Literal["clerical", "reading", "transliteration", "omission", "older_record"] | None = None
