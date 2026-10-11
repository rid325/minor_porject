"""Validated profile input used by the deterministic eligibility engine.

The values intentionally allow the explicit strings ``unknown`` and
``prefer_not_to_say``.  The engine treats both as unknown information rather
than silently turning them into a negative answer.  Extra fields are allowed
so the profile contract can grow without breaking older clients.
"""

from __future__ import annotations

from datetime import date
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


LooseBool = bool | str | None
LooseNumber = int | float | str | None


class ProfileSection(BaseModel):
    model_config = ConfigDict(extra="allow")


class LocationProfile(ProfileSection):
    state: str | None = None
    district: str | None = None
    residence_type: str | None = None
    domicile_status: str | None = None
    country: str | None = "India"


class PersonalProfile(ProfileSection):
    date_of_birth: date | None = None
    gender: str | None = None
    marital_status: str | None = None
    is_widow: LooseBool = None
    is_orphan: LooseBool = None
    dependent_status: str | None = None
    disability_status: str | None = None
    disability_percentage: LooseNumber = None


class HouseholdProfile(ProfileSection):
    size: LooseNumber = None
    applicant_annual_income: LooseNumber = None
    applicant_monthly_income: LooseNumber = None
    household_annual_income: LooseNumber = None
    income_period: str | None = "annual"
    currency: str | None = "INR"
    is_bpl: LooseBool = None
    ration_card_type: str | None = None
    ppp_status: str | None = None
    ppp_annual_income: LooseNumber = None
    has_lpg_connection: LooseBool = None
    poverty_category: str | None = None


class EducationProfile(ProfileSection):
    student_status: LooseBool = None
    study_level: str | None = None
    course: str | None = None
    institution_type: str | None = None
    institution_approved: LooseBool = None
    highest_qualification: str | None = None


class EmploymentProfile(ProfileSection):
    employment_status: str | None = None
    occupation: str | None = None
    worker_category: str | None = None
    worker_registration_status: str | None = None
    self_employed: LooseBool = None
    enterprise_status: str | None = None
    new_business: LooseBool = None
    unorganised_worker: LooseBool = None
    monthly_income: LooseNumber = None
    income_tax_payer: LooseBool = None
    epfo_member: LooseBool = None
    esic_member: LooseBool = None
    government_nps_member: LooseBool = None


class AgricultureAssetsProfile(ProfileSection):
    farmer_status: LooseBool = None
    landholding_status: str | None = None
    cultivable_land_acres: LooseNumber = None
    housing_status: str | None = None
    owns_house: LooseBool = None
    insurable_crop_interest: LooseBool = None
    crop_notified: LooseBool = None


class SocialProfile(ProfileSection):
    social_category: str | None = None
    existing_benefits: list[str] | str | None = None
    required_registration_status: str | None = None
    has_aadhaar: LooseBool = None
    has_bank_account: LooseBool = None
    has_mobile: LooseBool = None
    has_savings_bank_account: LooseBool = None
    has_other_bank_account: LooseBool = None
    residential_electricity_connection: LooseBool = None
    electricity_consumer_type: str | None = None


class ApplicantProfile(ProfileSection):
    """Normalized profile sent to ``POST /eligibility/check``."""

    location: LocationProfile = Field(default_factory=LocationProfile)
    personal: PersonalProfile = Field(default_factory=PersonalProfile)
    household: HouseholdProfile = Field(default_factory=HouseholdProfile)
    education: EducationProfile = Field(default_factory=EducationProfile)
    employment: EmploymentProfile = Field(default_factory=EmploymentProfile)
    agriculture: AgricultureAssetsProfile = Field(
        default_factory=AgricultureAssetsProfile
    )
    social: SocialProfile = Field(default_factory=SocialProfile)

    # A few clients naturally submit a derived age.  It is accepted for
    # display/backwards compatibility, but the service derives age from DOB
    # whenever a DOB is available.
    age: LooseNumber = None

    def as_dict(self) -> dict[str, Any]:
        return self.model_dump(mode="json", exclude_none=False)


class ProfileFieldOption(BaseModel):
    value: str
    label: str


class ProfileFieldDefinition(BaseModel):
    key: str
    label: str
    type: str
    required: bool = False
    sensitive: bool = False
    options: list[ProfileFieldOption] = Field(default_factory=list)
    help_text: str | None = None
    unknown_values: list[str] = Field(
        default_factory=lambda: ["unknown", "prefer_not_to_say"]
    )


class ProfileSectionDefinition(BaseModel):
    key: str
    label: str
    description: str | None = None
    fields: list[ProfileFieldDefinition]


class ProfileSchemaResponse(BaseModel):
    schema_version: str = "1.0"
    unknown_values: list[ProfileFieldOption]
    sections: list[ProfileSectionDefinition]
