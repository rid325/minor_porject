import { Profile } from "./types";

export const PROFILE_STORAGE_KEY = "scheme-finder-profile-v1";
export const RESULTS_STORAGE_KEY = "scheme-finder-results-v1";
export const PROFILE_OWNER_KEY = "scheme-finder-profile-owner-v1";

export function isInProfileRegion(jurisdiction: string, state: string) {
  const region = jurisdiction.split(";")[0].trim().toLowerCase();
  return !state.trim() || /^(?:(?:urban|rural) )?india\b/.test(region) || region.includes(state.trim().toLowerCase());
}

export function clearLocalProfileData(onlyIfAccountOwned = false) {
  try {
    if (onlyIfAccountOwned && !window.localStorage.getItem(PROFILE_OWNER_KEY)) return;
    window.localStorage.removeItem(PROFILE_STORAGE_KEY);
    window.localStorage.removeItem(RESULTS_STORAGE_KEY);
    window.localStorage.removeItem(PROFILE_OWNER_KEY);
  } catch { /* Storage can be unavailable in private browser modes. */ }
}

export const emptyProfile = (): Profile => ({
  scheme_answers: {},
  location: { state: "", district: "", pin: "", residence_type: "", domicile: "" },
  personal: { name: "", date_of_birth: "", gender: "", marital_status: "", disability_status: "", disability_percentage: "" },
  household: { size: "", applicant_income: "", family_income: "", income_period: "", bpl_status: "", ration_card: "", ppp_status: "", has_lpg_connection: "" },
  education: { student_status: "", study_level: "", institution_type: "" },
  employment: { employment_status: "", occupation: "", worker_registration: "", enterprise_status: "" },
  agriculture: { farmer_status: "", landholding_status: "", cultivable_land: "", insurable_crop_interest: "", crop_notified: "" },
  social: { social_category: "", existing_benefit: "", required_registration: "", has_savings_bank_account: "", residential_electricity_connection: "", electricity_consumer_type: "" },
});

export function mergeProfile(value: unknown): Profile {
  const blank = emptyProfile();
  if (!value || typeof value !== "object") return blank;
  const input = value as Record<string, unknown>;
  return {
    ...blank,
    ...input,
    scheme_answers: isRecord(input.scheme_answers) ? input.scheme_answers as unknown as Profile["scheme_answers"] : {},
    location: { ...blank.location, ...(isRecord(input.location) ? input.location : {}) },
    personal: { ...blank.personal, ...(isRecord(input.personal) ? input.personal : {}) },
    household: { ...blank.household, ...(isRecord(input.household) ? input.household : {}) },
    education: { ...blank.education, ...(isRecord(input.education) ? input.education : {}) },
    employment: { ...blank.employment, ...(isRecord(input.employment) ? input.employment : {}) },
    agriculture: { ...blank.agriculture, ...(isRecord(input.agriculture) ? input.agriculture : {}) },
    social: { ...blank.social, ...(isRecord(input.social) ? input.social : {}) },
  } as Profile;
}

function isRecord(value: unknown): value is Record<string, string> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

export function profileAnswerCount(profile: Profile) {
  const values: unknown[] = [
    ...Object.values(profile.location),
    ...Object.values(profile.personal),
    ...Object.values(profile.household),
    ...Object.values(profile.education),
    ...Object.values(profile.employment),
    ...Object.values(profile.agriculture),
    ...Object.values(profile.social),
  ];
  return values.filter((value) => value !== "" && value !== null && value !== undefined).length;
}

export function profileToApiPayload(profile: Profile) {
  const numberOrUndefined = (value: string) => value.trim() === "" ? undefined : Number(value);
  const yesNo = (value: string) => value === "yes" ? true : value === "no" ? false : value || undefined;
  const maritalStatus = profile.personal.marital_status;
  const isWidow = maritalStatus === "widowed" ? true : ["single", "married", "divorced"].includes(maritalStatus) ? false : undefined;
  return {
    ...profile,
    date_of_birth: profile.personal.date_of_birth || undefined,
    personal: {
      ...profile.personal,
      date_of_birth: profile.personal.date_of_birth || undefined,
      is_widow: isWidow,
    },
    location: {
      ...profile.location,
      domicile_status: profile.location.domicile || undefined,
    },
    household: {
      ...profile.household,
      applicant_annual_income: numberOrUndefined(profile.household.applicant_income),
      household_annual_income: numberOrUndefined(profile.household.family_income),
      size: numberOrUndefined(profile.household.size),
      is_bpl: yesNo(profile.household.bpl_status),
      ration_card_type: profile.household.ration_card || undefined,
      has_lpg_connection: yesNo(profile.household.has_lpg_connection),
    },
    education: {
      ...profile.education,
      student_status: yesNo(profile.education.student_status),
      course: profile.education.study_level || undefined,
    },
    employment: {
      ...profile.employment,
      worker_registration_status: profile.employment.worker_registration || undefined,
    },
    agriculture: {
      ...profile.agriculture,
      farmer_status: yesNo(profile.agriculture.farmer_status),
      insurable_crop_interest: yesNo(profile.agriculture.insurable_crop_interest),
      crop_notified: yesNo(profile.agriculture.crop_notified),
    },
    social: {
      ...profile.social,
      existing_benefits: profile.social.existing_benefit || undefined,
      required_registration_status: profile.social.required_registration || undefined,
      has_savings_bank_account: yesNo(profile.social.has_savings_bank_account),
      residential_electricity_connection: yesNo(profile.social.residential_electricity_connection),
    },
  };
}

