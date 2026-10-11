import { promises as fs } from "node:fs";
import path from "node:path";
import { NextRequest, NextResponse } from "next/server";
import { mockSchemes } from "@/lib/mock-schemes";
import { Scheme } from "@/lib/types";

function text(value: unknown, fallback = "") { return typeof value === "string" ? value : value == null ? fallback : String(value); }
function splitSources(value: unknown): string[] {
  if (Array.isArray(value)) return value.filter((item): item is string => typeof item === "string");
  return text(value).split(/[|;\n]/).map((item) => item.trim()).filter((item) => item.startsWith("http"));
}
function readiness(value: unknown): Scheme["application_readiness"] {
  const normalized = text(value).toLowerCase();
  if (normalized === "yes" || normalized.includes("ready") && !normalized.includes("not")) return "YES";
  if (normalized.includes("conditional") || normalized.includes("caution")) return "CONDITIONAL";
  if (normalized === "no" || normalized.includes("not ready") || normalized.includes("incomplete")) return "NO";
  return "UNKNOWN";
}
function mapRow(row: Record<string, unknown>): Scheme {
  return {
    scheme_id: text(row.scheme_id, "scheme"), name: text(row.scheme_name, "Untitled scheme"), jurisdiction: text(row.jurisdiction, "India"), category: text(row.category, "Government support"),
    administering_authority: text(row.administering_body), summary: text(row.benefit_summary, "Government support scheme"), benefit: text(row.benefit_summary), eligibility_text: text(row.eligibility_text), documents_text: text(row.documents_required), application_mode: text(row.application_mode), application_url: text(row.application_url) || undefined,
    application_steps: text(row.application_steps), deadline_or_timing: text(row.deadline_or_renewal), tracking_method: text(row.tracking_grievance), important_caution: text(row.eligibility_unresolved || row.next_review_action), source_urls: splitSources(`${text(row.source_url)} | ${text(row.additional_sources)}`), source_authority: text(row.source_authority), research_status: text(row.extraction_status), application_readiness: readiness(row.application_ready), last_checked: text(row.last_checked), eligibility_unresolved: text(row.eligibility_unresolved), exclusions_text: text(row.exclusions_text),
  };
}

async function loadRows(): Promise<Scheme[]> {
  const candidateRoots = [path.resolve(process.cwd(), "..", "work"), path.resolve(process.cwd(), "work")];
  const rows: Scheme[] = [...mockSchemes];
  for (const root of candidateRoots) {
    try {
      const files = (await fs.readdir(/* turbopackIgnore: true */ root)).filter((file) => file.endsWith(".json") && file.includes("batch"));
      for (const file of files) {
        const content = JSON.parse(await fs.readFile(path.join(/* turbopackIgnore: true */ root, file), "utf8"));
        if (Array.isArray(content)) rows.push(...content.map((row) => mapRow(row as Record<string, unknown>)));
      }
      break;
    } catch {
      // Try the next root; deployed previews use the seed rows above.
    }
  }
  return Array.from(new Map(rows.map((scheme) => [scheme.scheme_id, scheme])).values());
}

export async function GET(request: NextRequest) {
  const query = request.nextUrl.searchParams;
  const search = (query.get("search") || "").toLowerCase();
  const jurisdiction = (query.get("jurisdiction") || "").toLowerCase();
  const category = query.get("category") || "";
  const readinessFilter = query.get("readiness") || "";
  const schemes = (await loadRows()).filter((scheme) => {
    const corpus = `${scheme.name} ${scheme.summary} ${scheme.category} ${scheme.jurisdiction}`.toLowerCase();
    return (!search || corpus.includes(search)) && (!jurisdiction || scheme.jurisdiction.toLowerCase().includes(jurisdiction)) && (!category || scheme.category === category) && (!readinessFilter || scheme.application_readiness === readinessFilter);
  });
  return NextResponse.json({ items: schemes, total: schemes.length, source: "local-workbook-preview" });
}
