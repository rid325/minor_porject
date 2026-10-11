import { emptyProfile, profileToApiPayload } from "./profile";
import { EligibilityResponse, EligibilityResult, Profile, Readiness, Scheme } from "./types";
import { mockSchemes } from "./mock-schemes";

const API_BASE = (process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000").replace(/\/$/, "");

function asArray(value: unknown): unknown[] {
  if (Array.isArray(value)) return value;
  if (value && typeof value === "object") {
    const record = value as Record<string, unknown>;
    for (const key of ["items", "schemes", "data", "results"]) {
      if (Array.isArray(record[key])) return record[key] as unknown[];
    }
  }
  return [];
}

function text(value: unknown, fallback = "") {
  return typeof value === "string" ? value : value == null ? fallback : String(value);
}

function splitSources(value: unknown): string[] {
  if (Array.isArray(value)) return value.filter((item): item is string => typeof item === "string" && item.length > 0);
  return text(value).split(/[|;\n]/).map((item) => item.trim()).filter(Boolean).filter((item) => item.startsWith("http"));
}

function readiness(value: unknown): Readiness {
  const normalized = text(value).toLowerCase();
  if (normalized === "yes" || normalized.includes("ready")) return "YES";
  if (normalized === "conditional" || normalized.includes("caution")) return "CONDITIONAL";
  if (normalized === "no" || normalized.includes("not ready") || normalized.includes("incomplete")) return "NO";
  return "UNKNOWN";
}

export function normalizeScheme(value: unknown): Scheme {
  const raw = (value || {}) as Record<string, unknown>;
  const sourceUrls = splitSources(raw.source_urls ?? raw.sources ?? raw.source_url ?? raw.additional_sources);
  const resolvedReadiness = readiness(raw.application_readiness ?? raw.application_ready ?? raw.readiness);
  return {
    scheme_id: text(raw.scheme_id ?? raw.id, cryptoSafeId(raw.name)),
    name: text(raw.name ?? raw.scheme_name, "Untitled scheme"),
    jurisdiction: text(raw.jurisdiction, "India"),
    category: text(raw.category, "Government support"),
    administering_authority: text(raw.administering_authority ?? raw.administering_body),
    summary: text(raw.summary ?? raw.benefit_summary, "Government support scheme"),
    benefit: text(raw.benefit ?? raw.benefit_summary),
    eligibility_text: text(raw.eligibility_text ?? raw.eligibility),
    documents_text: text(raw.documents_text ?? raw.documents_required),
    application_mode: text(raw.application_mode, "Check official route"),
    application_url: text(raw.application_url) || undefined,
    application_steps: text(raw.application_steps),
    deadline_or_timing: text(raw.deadline_or_timing ?? raw.deadline_or_renewal),
    tracking_method: text(raw.tracking_method ?? raw.tracking_grievance),
    important_caution: text(raw.important_caution ?? raw.eligibility_unresolved ?? raw.next_review_action),
    source_urls: sourceUrls,
    source_authority: text(raw.source_authority),
    research_status: text(raw.research_status ?? raw.extraction_status),
    application_readiness: resolvedReadiness,
    last_checked: text(raw.last_checked),
    eligibility_unresolved: text(raw.eligibility_unresolved),
    exclusions_text: text(raw.exclusions_text),
    target_group: text(raw.target_group ?? raw.who_should_try),
  };
}

function cryptoSafeId(value: unknown) {
  return text(value, "scheme").toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "");
}

async function getJson(url: string, init?: RequestInit) {
  const response = await fetch(url, { ...init, headers: { Accept: "application/json", ...(init?.headers || {}) }, cache: "no-store" });
  if (!response.ok) throw new Error(`Request failed (${response.status})`);
  return response.json();
}

export type SchemeQuery = { search?: string; jurisdiction?: string; category?: string; readiness?: string };

export async function getSchemes(query: SchemeQuery = {}): Promise<Scheme[]> {
  const params = new URLSearchParams();
  // The catalogue screen is intentionally a complete 75-scheme view. The
  // backend defaults to a smaller page for general API consumers, so request
  // the prototype's full catalogue explicitly here.
  params.set("page_size", "100");
  if (query.search) params.set("search", query.search);
  if (query.jurisdiction) params.set("jurisdiction", query.jurisdiction);
  if (query.category) params.set("category", query.category);
  if (query.readiness) params.set("readiness", query.readiness);
  try {
    const data = await getJson(`${API_BASE}/api/v1/schemes${params.size ? `?${params}` : ""}`);
    const schemes = asArray(data).map(normalizeScheme);
    if (schemes.length) return schemes;
  } catch {
    // The local route below makes the preview work before FastAPI is running.
  }
  try {
    const data = await getJson(`/api/v1/schemes?mock=1${params.size ? `&${params}` : ""}`);
    const schemes = asArray(data).map(normalizeScheme);
    if (schemes.length) return schemes;
  } catch {
    // Use the in-bundle seed as the final offline fallback.
  }
  return filterSchemes(mockSchemes, query);
}

export async function getScheme(id: string): Promise<Scheme | undefined> {
  try {
    const data = await getJson(`${API_BASE}/api/v1/schemes/${encodeURIComponent(id)}`);
    return normalizeScheme(data?.scheme ?? data?.data ?? data);
  } catch {
    try {
      const data = await getJson(`/api/v1/schemes/${encodeURIComponent(id)}?mock=1`);
      return normalizeScheme(data?.scheme ?? data?.data ?? data);
    } catch {
      return mockSchemes.find((scheme) => scheme.scheme_id === id);
    }
  }
}

function filterSchemes(schemes: Scheme[], query: SchemeQuery) {
  const search = (query.search || "").toLowerCase();
  return schemes.filter((scheme) => {
    const matchesSearch = !search || `${scheme.name} ${scheme.summary} ${scheme.category} ${scheme.jurisdiction}`.toLowerCase().includes(search);
    const matchesJurisdiction = !query.jurisdiction || scheme.jurisdiction.toLowerCase().includes(query.jurisdiction.toLowerCase());
    const matchesCategory = !query.category || scheme.category === query.category;
    const matchesReadiness = !query.readiness || scheme.application_readiness === query.readiness;
    return matchesSearch && matchesJurisdiction && matchesCategory && matchesReadiness;
  });
}

export async function checkEligibility(profile: Profile): Promise<EligibilityResponse> {
  try {
    const data = await getJson(`${API_BASE}/api/v1/eligibility/check`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(profileToApiPayload(profile)),
    });
    return normalizeEligibilityResponse(data);
  } catch {
    let schemes = mockSchemes;
    try {
      schemes = await getSchemes();
    } catch {
      // Keep the seed data.
    }
    return localEligibility(profile, schemes);
  }
}

function normalizeEligibilityResponse(value: unknown): EligibilityResponse {
  const raw = (value || {}) as Record<string, unknown>;
  const rows = asArray(value).length ? asArray(value) : asArray(raw.results ?? raw.items ?? raw.data);
  return {
    results: rows.map((item) => {
      const row = item as Record<string, unknown>;
      const scheme = normalizeScheme(row.scheme ?? row);
      const result = normalizeResult(row.result ?? row.status ?? row.bucket);
      const reasons = normalizeReasons(row.reasons ?? row.explanations ?? row.conditions);
      return { scheme, result, reasons, passed: normalizeReasons(row.passed), failed: normalizeReasons(row.failed), unknown: normalizeReasons(row.unknown), external_checks: normalizeReasons(row.external_checks) };
    }),
    profile_version: text(raw.profile_version),
    rule_set_version: text(raw.rule_set_version),
    generated_at: text(raw.generated_at),
  };
}

function normalizeResult(value: unknown): EligibilityResult["result"] {
  const normalized = text(value).toLowerCase().replace(/[ -]/g, "_");
  if (normalized.includes("eligible") && !normalized.includes("not")) return "likely_eligible";
  if (normalized.includes("not_eligible") || normalized.includes("ineligible")) return "likely_not_eligible";
  if (normalized.includes("information_only") || normalized.includes("information")) return "information_only";
  return "needs_information";
}

function normalizeReasons(value: unknown): EligibilityResult["reasons"] {
  if (!Array.isArray(value)) return [];
  return value.map((reason) => {
    if (typeof reason === "string") return { message: reason };
    const row = (reason || {}) as Record<string, unknown>;
    return { label: text(row.label ?? row.field), message: text(row.message ?? row.reason ?? row.explanation, "Review this condition."), status: text(row.status) as EligibilityResult["reasons"][number]["status"], source_url: text(row.source_url) || undefined };
  });
}

function localEligibility(profile: Profile, schemes: Scheme[]): EligibilityResponse {
  const answered = Object.values(profile).flatMap((section) => Object.values(section)).filter((value) => value !== "" && value !== null && value !== undefined).length;
  const hasLocation = Boolean(profile.location.state);
  const age = profile.personal.date_of_birth ? calculateAge(profile.personal.date_of_birth) : null;
  const income = Number(profile.household.family_income || 0);
  const results: EligibilityResult[] = schemes.map((scheme) => {
    const allReasons: EligibilityResult["reasons"] = [];
    const textCorpus = `${scheme.name} ${scheme.category} ${scheme.eligibility_text}`.toLowerCase();
    let result: EligibilityResult["result"] = "needs_information";
    if (scheme.application_readiness === "NO" || scheme.application_readiness === "UNKNOWN") {
      result = "information_only";
      allReasons.push({ message: "This record still needs source or application-route review.", status: "EXTERNAL_CHECK" });
    } else if (hasLocation && scheme.jurisdiction.toLowerCase().includes(profile.location.state.toLowerCase())) {
      result = "likely_eligible";
      allReasons.push({ message: "Your state matches this scheme’s listed jurisdiction.", status: "PASS" });
    } else if (hasLocation && scheme.jurisdiction.toLowerCase().includes("india")) {
      result = answered > 5 ? "likely_eligible" : "needs_information";
      allReasons.push({ message: "This scheme is available nationally; a few conditions still need verification.", status: answered > 5 ? "PASS" : "UNKNOWN" });
    } else if (hasLocation) {
      result = "likely_not_eligible";
      allReasons.push({ message: `The listed jurisdiction is ${scheme.jurisdiction}; your profile says ${profile.location.state}.`, status: "FAIL" });
    } else {
      allReasons.push({ message: "Add your state to check jurisdiction and local conditions.", status: "UNKNOWN" });
    }
    if (textCorpus.includes("farmer") || textCorpus.includes("agriculture")) {
      if (profile.agriculture.farmer_status === "yes") allReasons.push({ message: "Farmer status is marked yes.", status: "PASS" });
      else if (!profile.agriculture.farmer_status) allReasons.push({ message: "Tell us whether you are a farmer for the agriculture check.", status: "UNKNOWN" });
    }
    if (textCorpus.includes("income") && !profile.household.family_income) allReasons.push({ message: "Family income is needed for this scheme’s income condition.", status: "UNKNOWN" });
    if (textCorpus.includes("widow") && profile.personal.marital_status === "widowed") allReasons.push({ message: "Your profile marks you as widowed.", status: "PASS" });
    if (textCorpus.includes("widow") && profile.personal.marital_status && profile.personal.marital_status !== "widowed") { result = "likely_not_eligible"; allReasons.push({ message: "This scheme is for widows; your marital-status answer does not match.", status: "FAIL" }); }
    if (age !== null && textCorpus.includes("18") && age < 18) { result = "likely_not_eligible"; allReasons.push({ message: "The listed minimum age is 18.", status: "FAIL" }); }
    if (income > 0 && textCorpus.includes("3 lakh") && income > 300000) { result = "likely_not_eligible"; allReasons.push({ message: "The listed family-income ceiling is INR 3 lakh per year.", status: "FAIL" }); }
    return { scheme, result, reasons: allReasons };
  });
  return { results, profile_version: "local-preview", rule_set_version: "mock-v1", generated_at: new Date().toISOString() };
}

function calculateAge(date: string) {
  const birth = new Date(`${date}T00:00:00`);
  if (Number.isNaN(birth.getTime())) return null;
  const today = new Date();
  let age = today.getFullYear() - birth.getFullYear();
  const beforeBirthday = today.getMonth() < birth.getMonth() || (today.getMonth() === birth.getMonth() && today.getDate() < birth.getDate());
  if (beforeBirthday) age -= 1;
  return age;
}

export { emptyProfile };
