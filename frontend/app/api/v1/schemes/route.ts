import { NextRequest, NextResponse } from "next/server";
import seed from "../../../../../backend/data/schemes.seed.json";
import { normalizeScheme } from "@/lib/api";

export async function GET(request: NextRequest) {
  const query = request.nextUrl.searchParams;
  const search = (query.get("search") || "").toLowerCase();
  const jurisdiction = (query.get("jurisdiction") || "").toLowerCase();
  const category = query.get("category") || "";
  const readinessFilter = query.get("readiness") || "";
  const schemes = seed.schemes.map(normalizeScheme).filter((scheme) => {
    const corpus = `${scheme.name} ${scheme.summary} ${scheme.category} ${scheme.jurisdiction}`.toLowerCase();
    return (!search || corpus.includes(search)) && (!jurisdiction || scheme.jurisdiction.toLowerCase().includes(jurisdiction)) && (!category || scheme.category === category) && (!readinessFilter || scheme.application_readiness === readinessFilter);
  });
  return NextResponse.json({ items: schemes, total: schemes.length, source: "checked-in-seed" });
}
