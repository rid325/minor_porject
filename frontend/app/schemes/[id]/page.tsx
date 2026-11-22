import SchemeDetail from "@/components/SchemeDetail";

export default async function SchemeDetailPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  return <SchemeDetail id={decodeURIComponent(id)} />;
}
