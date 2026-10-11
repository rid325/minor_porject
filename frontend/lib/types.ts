export type Readiness = "YES" | "CONDITIONAL" | "NO" | "UNKNOWN";

export type Scheme = {
  scheme_id: string;
  name: string;
  jurisdiction: string;
  category: string;
  administering_authority?: string;
  summary: string;
  benefit: string;
  eligibility_text: string;
  documents_text: string;
  application_mode: string;
  application_url?: string;
  application_steps: string;
  deadline_or_timing?: string;
  tracking_method?: string;
  important_caution?: string;
  source_urls: string[];
  source_authority?: string;
  research_status?: string;
  application_readiness: Readiness;
  last_checked?: string;
  eligibility_unresolved?: string;
  exclusions_text?: string;
  target_group?: string;
};

export type ProfileValue = string | number | boolean | null | undefined;

export type Profile = {
  location: {
    state: string;
    district: string;
    residence_type: "rural" | "urban" | "";
    domicile: "yes" | "no" | "unknown" | "";
  };
  personal: {
    date_of_birth: string;
    gender: "woman" | "man" | "non_binary" | "prefer_not_to_say" | "";
    marital_status: "single" | "married" | "widowed" | "divorced" | "";
    disability_status: "yes" | "no" | "unknown" | "";
    disability_percentage: string;
  };
  household: {
    size: string;
    applicant_income: string;
    family_income: string;
    income_period: "annual" | "monthly" | "unknown" | "";
    bpl_status: "yes" | "no" | "unknown" | "";
    ration_card: "yes" | "no" | "unknown" | "";
    ppp_status: "yes" | "no" | "unknown" | "";
  };
  education: {
    student_status: "yes" | "no" | "unknown" | "";
    study_level: string;
    institution_type: string;
  };
  employment: {
    employment_status: "employed" | "self_employed" | "unemployed" | "student" | "retired" | "unknown" | "";
    occupation: string;
    worker_registration: "yes" | "no" | "unknown" | "";
    enterprise_status: "yes" | "no" | "unknown" | "";
  };
  agriculture: {
    farmer_status: "yes" | "no" | "unknown" | "";
    landholding_status: "owned" | "leased" | "none" | "unknown" | "";
    cultivable_land: "yes" | "no" | "unknown" | "";
  };
  social: {
    social_category: "general" | "sc" | "st" | "obc" | "other" | "prefer_not_to_say" | "";
    existing_benefit: "yes" | "no" | "unknown" | "";
    required_registration: "yes" | "no" | "unknown" | "";
  };
};

export type ResultBucket = "likely_eligible" | "needs_information" | "likely_not_eligible" | "information_only";

export type EligibilityReason = {
  label?: string;
  message: string;
  status?: "PASS" | "FAIL" | "UNKNOWN" | "EXTERNAL_CHECK";
  source_url?: string;
};

export type EligibilityResult = {
  scheme: Scheme;
  result: ResultBucket;
  reasons: EligibilityReason[];
  passed?: EligibilityReason[];
  failed?: EligibilityReason[];
  unknown?: EligibilityReason[];
  external_checks?: EligibilityReason[];
};

export type EligibilityResponse = {
  results: EligibilityResult[];
  profile_version?: string;
  rule_set_version?: string;
  generated_at?: string;
};
