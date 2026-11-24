"""Structured evidence accepted by the application document checker."""

from datetime import date
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

DocumentType = Literal["identity", "residence", "age", "bank", "income", "family_id", "category", "disability", "other", "unknown"]
FieldName = Literal[
    "name", "father_name", "mother_name", "date_of_birth", "gender", "place_of_birth",
    "address", "house_number", "street", "sector", "village", "city", "state", "district", "pin",
    "annual_household_income", "social_category", "disability_percentage",
]
DocumentLanguage = Literal["auto", "en", "hi", "pa"]
ShortText = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=120)]


class EvidenceField(BaseModel):
    model_config = ConfigDict(extra="forbid")

    value: ShortText
    original_value: ShortText | None = None
    date_format_uncertain: bool = False
    user_confirmed: bool = False
    page: int = Field(ge=1, le=500)
    bounding_box: tuple[int, int, int, int] | None = None
    ocr_confidence: float | None = Field(default=None, ge=0, le=1)
    extraction_confidence: float | None = Field(default=None, ge=0, le=1)


class DocumentEvidence(BaseModel):
    model_config = ConfigDict(extra="forbid")

    document_type: DocumentType
    readable: bool = True
    missing_pages: bool = False
    expires_on: date | None = None
    issued_on: date | None = None
    fields: dict[FieldName, EvidenceField] = Field(default_factory=dict)


class DocumentCheckRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    consent: Literal[True]
    documents: list[DocumentEvidence] = Field(max_length=20)
    preparation: dict[str, Literal["ready", "missing", "unsure", "inapplicable"]] = Field(default_factory=dict, max_length=150)
    compare_unconfirmed: bool = False


