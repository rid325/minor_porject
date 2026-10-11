import { NextRequest, NextResponse } from "next/server";
import { GET as getSchemes } from "../route";

export async function GET(request: NextRequest, context: { params: Promise<{ id: string }> }) {
  const { id } = await context.params;
  const response = await getSchemes(new NextRequest(new URL(`/api/v1/schemes?search=`, request.url)));
  const data = await response.json();
  const scheme = data.items?.find((item: { scheme_id: string }) => item.scheme_id === id);
  if (!scheme) return NextResponse.json({ detail: "Scheme not found" }, { status: 404 });
  return NextResponse.json(scheme);
}
