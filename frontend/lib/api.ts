import { emptyProfile, profileToApiPayload } from "./profile";
import { EligibilityResponse, EligibilityResult, Profile, Readiness, Scheme } from "./types";


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
  const items = Array.isArray(value) ? value : [value];
  return items.flatMap(item => text(item && typeof item === "object" ? item.url : item).split(/[|;\n]/))
    .map(url => url.trim()).filter(url => URL.canParse(url) && /^https?:\/\//i.test(url));
}

function readiness(value: unknown): Readiness {
  const normalized = text(value).toLowerCase();
  if (normalized === "yes" || (normalized.includes("ready") && !normalized.includes("not ready"))) return "YES";
  if (normalized === "conditional" || normalized.includes("caution")) return "CONDITIONAL";
  if (normalized === "no" || normalized.includes("not ready") || normalized.includes("incomplete")) return "NO";
  return "UNKNOWN";
}

export function normalizeScheme(value: unknown): Scheme {
  const raw = (value || {}) as Record<string, unknown>;
  const sourceUrls = [...new Set([raw.source_urls, raw.sources, raw.source_url, raw.additional_sources].flatMap(splitSources))];
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
    application_url: splitSources(raw.application_url)[0],
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
    normalized_conditions: Array.isArray(raw.normalized_conditions) ? raw.normalized_conditions as Scheme["normalized_conditions"] : [],
    condition_schema_version: text(raw.condition_schema_version) || undefined,
    condition_review_state: text(raw.condition_review_state) as Scheme["condition_review_state"],
    target_group: text(raw.target_group ?? raw.who_should_try),
    application_guide: raw.application_guide && typeof raw.application_guide === "object"
      ? raw.application_guide as Scheme["application_guide"]
      : undefined,
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
    return schemes;
  } catch {
    // The local route below makes the preview work before FastAPI is running.
  }
  try {
    const data = await getJson(`/api/v1/schemes?mock=1${params.size ? `&${params}` : ""}`);
    const schemes = asArray(data).map(normalizeScheme);
    return schemes;
  } catch {
    throw new Error("Could not load the scheme catalogue.");
  }
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
      return undefined;
    }
  }
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
    throw new Error("Eligibility checking is unavailable. Your answers are saved. Please retry when the API is available.");
  }
}

function normalizeEligibilityResponse(value: unknown): EligibilityResponse {
  const raw = (value || {}) as Record<string, unknown>;
  const rows = asArray(value).length ? asArray(value) : asArray(raw.results ?? raw.items ?? raw.data);
  return {
    results: rows.map((item) => {
      const row = item as Record<string, unknown>;
      const scheme = normalizeScheme(row.scheme ?? row);
      const result = normalizeResult(row.result ?? row.category ?? row.display_label ?? row.status ?? row.bucket);
      const passed = normalizeReasons(row.passed);
      const failed = normalizeReasons(row.failed);
      const unknown = normalizeReasons(row.unknown ?? row.missing);
      const externalChecks = normalizeReasons(row.external_checks);
      const reasons = normalizeReasons(row.reasons ?? row.explanations ?? row.conditions);
      const totalConditions = passed.length + failed.length + unknown.length;
      return {
        scheme, result,
        rule_review_state: text(row.rule_review_state) as EligibilityResult["rule_review_state"],
        warnings: asArray(row.warnings).map((warning) => text(warning)).filter(Boolean),
        reasons: reasons.length ? reasons : [...passed, ...failed, ...unknown, ...externalChecks],
        passed, failed, unknown, external_checks: externalChecks,
        matched_conditions: passed.length,
        total_conditions: totalConditions,
        matched_requirement_groups: Number(row.matched_requirement_groups ?? passed.length),
        total_requirement_groups: Number(row.total_requirement_groups ?? totalConditions),
      };
    }),
    profile_version: text(raw.profile_version),
    rule_set_version: text(raw.rule_set_version),
    generated_at: text(raw.generated_at),
  };
}

function normalizeResult(value: unknown): EligibilityResult["result"] {
  const normalized = text(value).toLowerCase().replace(/[ -]/g, "_");
  if (normalized.includes("eligible") && !normalized.includes("not") && !normalized.includes("ineligible")) return "likely_eligible";
  if (normalized.includes("not_eligible") || normalized.includes("ineligible")) return "likely_not_eligible";
  if (normalized.includes("needs_more_information") || normalized.includes("needs_information")) return "needs_information";
  if (normalized.includes("information_only") || normalized === "information") return "information_only";
  return "needs_information";
}

function normalizeReasons(value: unknown): EligibilityResult["reasons"] {
  if (!Array.isArray(value)) return [];
  return value.map((reason) => {
    if (typeof reason === "string") return { message: reason };
    const row = (reason || {}) as Record<string, unknown>;
    return { label: text(row.label ?? row.field ?? row.rule_id), message: text(row.message ?? row.reason ?? row.explanation ?? row.description ?? row.missing_reason ?? row.failure_reason, "Review this condition."), status: text(row.status).toUpperCase() as EligibilityResult["reasons"][number]["status"], source_url: text(row.source_url) || undefined };
  });
}

export { emptyProfile };
