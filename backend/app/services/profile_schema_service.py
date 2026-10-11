"""Human-facing profile field dictionary for the first prototype."""

from __future__ import annotations

from ..schemas.profile import (
    ProfileFieldDefinition,
    ProfileFieldOption,
    ProfileSchemaResponse,
    ProfileSectionDefinition,
)


def _options(*values: tuple[str, str]) -> list[ProfileFieldOption]:
    return [ProfileFieldOption(value=value, label=label) for value, label in values]


YES_NO = _options(("yes", "Yes"), ("no", "No"))


def get_profile_schema() -> ProfileSchemaResponse:
    return ProfileSchemaResponse(
        schema_version="1.0",
        unknown_values=[
            ProfileFieldOption(value="unknown", label="I do not know"),
            ProfileFieldOption(value="prefer_not_to_say", label="Prefer not to say"),
        ],
        sections=[
            ProfileSectionDefinition(
                key="location",
                label="Location",
                description="Location and residence questions used by state and local schemes.",
                fields=[
                    ProfileFieldDefinition(
                        key="location.state",
                        label="State or Union Territory",
                        type="select",
                        sensitive=False,
                        options=_options(
                            ("Haryana", "Haryana"),
                            ("Himachal Pradesh", "Himachal Pradesh"),
                            ("Punjab", "Punjab"),
                            ("Chandigarh", "Chandigarh"),
                            ("other", "Other state/UT"),
                        ),
                    ),
                    ProfileFieldDefinition(
                        key="location.district",
                        label="District",
                        type="text",
                    ),
                    ProfileFieldDefinition(
                        key="location.residence_type",
                        label="Residence type",
                        type="select",
                        options=_options(("rural", "Rural"), ("urban", "Urban")),
                    ),
                    ProfileFieldDefinition(
                        key="location.domicile_status",
                        label="Domicile/residence status",
                        type="select",
                        options=_options(
                            ("domiciled", "Domiciled"),
                            ("resident", "Resident"),
                            ("not_domiciled", "Not domiciled"),
                        ),
                    ),
                    ProfileFieldDefinition(
                        key="location.country",
                        label="Country of residence/citizenship",
                        type="text",
                        help_text="India is pre-filled for the Indian government scheme catalogue.",
                    ),
                ],
            ),
            ProfileSectionDefinition(
                key="personal",
                label="Personal details",
                description="Only answer sensitive questions when they are relevant to a scheme you want to check.",
                fields=[
                    ProfileFieldDefinition(
                        key="personal.date_of_birth",
                        label="Date of birth",
                        type="date",
                    ),
                    ProfileFieldDefinition(
                        key="personal.gender",
                        label="Gender",
                        type="select",
                        sensitive=True,
                        options=_options(
                            ("female", "Female/woman"),
                            ("male", "Male/man"),
                            ("other", "Another identity"),
                        ),
                    ),
                    ProfileFieldDefinition(
                        key="personal.marital_status",
                        label="Marital status",
                        type="select",
                        sensitive=True,
                        options=_options(
                            ("married", "Married"),
                            ("unmarried", "Unmarried"),
                            ("widowed", "Widowed"),
                            ("divorced", "Divorced/separated"),
                        ),
                    ),
                    ProfileFieldDefinition(
                        key="personal.is_widow",
                        label="Is the applicant a widow?",
                        type="boolean",
                        sensitive=True,
                        options=YES_NO,
                    ),
                    ProfileFieldDefinition(
                        key="personal.disability_status",
                        label="Disability status",
                        type="select",
                        sensitive=True,
                        options=_options(
                            ("none", "No known disability"),
                            ("person_with_disability", "Person with disability"),
                        ),
                    ),
                    ProfileFieldDefinition(
                        key="personal.disability_percentage",
                        label="Disability percentage (if known)",
                        type="number",
                        sensitive=True,
                    ),
                ],
            ),
            ProfileSectionDefinition(
                key="household",
                label="Household and income",
                description="Use the period and unit shown by the question; unknown and zero are different answers.",
                fields=[
                    ProfileFieldDefinition(key="household.size", label="Household size", type="number"),
                    ProfileFieldDefinition(
                        key="household.household_annual_income",
                        label="Household annual income (INR)",
                        type="number",
                    ),
                    ProfileFieldDefinition(
                        key="household.applicant_annual_income",
                        label="Applicant annual income (INR)",
                        type="number",
                    ),
                    ProfileFieldDefinition(
                        key="household.applicant_monthly_income",
                        label="Applicant monthly income (INR)",
                        type="number",
                    ),
                    ProfileFieldDefinition(
                        key="household.is_bpl",
                        label="BPL status",
                        type="boolean",
                        sensitive=True,
                        options=YES_NO,
                    ),
                    ProfileFieldDefinition(
                        key="household.ration_card_type",
                        label="Ration-card type",
                        type="text",
                        sensitive=True,
                    ),
                    ProfileFieldDefinition(
                        key="household.ppp_status",
                        label="PPP/Family ID status",
                        type="select",
                        sensitive=True,
                        options=_options(
                            ("verified", "Verified"),
                            ("not_verified", "Not verified"),
                            ("not_available", "Not available"),
                        ),
                    ),
                    ProfileFieldDefinition(
                        key="household.has_lpg_connection",
                        label="Does the household already have an LPG connection?",
                        type="boolean",
                        options=YES_NO,
                    ),
                    ProfileFieldDefinition(
                        key="household.poverty_category",
                        label="Notified deprivation/category route (if known)",
                        type="text",
                        sensitive=True,
                    ),
                ],
            ),
            ProfileSectionDefinition(
                key="education",
                label="Education",
                fields=[
                    ProfileFieldDefinition(
                        key="education.student_status",
                        label="Is the applicant currently a student?",
                        type="boolean",
                        options=YES_NO,
                    ),
                    ProfileFieldDefinition(key="education.study_level", label="Study level", type="text"),
                    ProfileFieldDefinition(key="education.course", label="Course or trade", type="text"),
                    ProfileFieldDefinition(
                        key="education.institution_type",
                        label="Institution type",
                        type="text",
                    ),
                    ProfileFieldDefinition(
                        key="education.institution_approved",
                        label="Is the institution approved/recognised?",
                        type="boolean",
                        options=YES_NO,
                    ),
                ],
            ),
            ProfileSectionDefinition(
                key="employment",
                label="Employment and occupation",
                fields=[
                    ProfileFieldDefinition(key="employment.employment_status", label="Employment status", type="text"),
                    ProfileFieldDefinition(key="employment.occupation", label="Occupation", type="text"),
                    ProfileFieldDefinition(key="employment.worker_category", label="Worker category", type="text"),
                    ProfileFieldDefinition(
                        key="employment.unorganised_worker",
                        label="Is the applicant an unorganised worker?",
                        type="boolean",
                        options=YES_NO,
                    ),
                    ProfileFieldDefinition(
                        key="employment.monthly_income",
                        label="Worker monthly income (INR)",
                        type="number",
                    ),
                    ProfileFieldDefinition(
                        key="employment.income_tax_payer",
                        label="Is the applicant an income-tax payer?",
                        type="boolean",
                        sensitive=True,
                        options=YES_NO,
                    ),
                    ProfileFieldDefinition(
                        key="employment.epfo_member",
                        label="Covered by EPFO?",
                        type="boolean",
                        sensitive=True,
                        options=YES_NO,
                    ),
                    ProfileFieldDefinition(
                        key="employment.esic_member",
                        label="Covered by ESIC?",
                        type="boolean",
                        sensitive=True,
                        options=YES_NO,
                    ),
                ],
            ),
            ProfileSectionDefinition(
                key="agriculture",
                label="Agriculture and assets",
                fields=[
                    ProfileFieldDefinition(
                        key="agriculture.farmer_status",
                        label="Is the applicant a farmer?",
                        type="boolean",
                        options=YES_NO,
                    ),
                    ProfileFieldDefinition(
                        key="agriculture.landholding_status",
                        label="Landholding/cultivation status",
                        type="select",
                        options=_options(
                            ("owner", "Owner/landholder"),
                            ("cultivator", "Cultivator"),
                            ("tenant", "Tenant/sharecropper"),
                            ("landless", "Landless"),
                        ),
                    ),
                    ProfileFieldDefinition(
                        key="agriculture.insurable_crop_interest",
                        label="Insurable crop interest?",
                        type="boolean",
                        options=YES_NO,
                    ),
                    ProfileFieldDefinition(
                        key="agriculture.crop_notified",
                        label="Crop/area notified for the season?",
                        type="boolean",
                        options=YES_NO,
                    ),
                ],
            ),
            ProfileSectionDefinition(
                key="social",
                label="Social and scheme-specific conditions",
                description="These fields are only sent for evaluation; the API does not save the profile.",
                fields=[
                    ProfileFieldDefinition(
                        key="social.social_category",
                        label="Social category (when relevant)",
                        type="select",
                        sensitive=True,
                        options=_options(
                            ("sc", "Scheduled Caste"),
                            ("st", "Scheduled Tribe"),
                            ("obc", "Other Backward Class"),
                            ("general", "General"),
                            ("other", "Other"),
                        ),
                    ),
                    ProfileFieldDefinition(
                        key="social.has_savings_bank_account",
                        label="Has a savings bank/post-office account?",
                        type="boolean",
                        options=YES_NO,
                    ),
                    ProfileFieldDefinition(
                        key="social.has_other_bank_account",
                        label="Already has another bank account?",
                        type="boolean",
                        options=YES_NO,
                    ),
                    ProfileFieldDefinition(
                        key="social.residential_electricity_connection",
                        label="Has an eligible residential electricity connection?",
                        type="boolean",
                        options=YES_NO,
                    ),
                    ProfileFieldDefinition(
                        key="social.electricity_consumer_type",
                        label="Electricity consumer type",
                        type="select",
                        options=_options(
                            ("residential", "Residential/domestic"),
                            ("commercial", "Commercial"),
                            ("industrial", "Industrial"),
                        ),
                    ),
                    ProfileFieldDefinition(
                        key="social.has_aadhaar",
                        label="Has Aadhaar or accepted identity document?",
                        type="boolean",
                        sensitive=True,
                        options=YES_NO,
                    ),
                    ProfileFieldDefinition(
                        key="social.has_bank_account",
                        label="Has a bank account?",
                        type="boolean",
                        options=YES_NO,
                    ),
                ],
            ),
        ],
    )
