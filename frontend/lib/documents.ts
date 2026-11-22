export const documentApi = (process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000").replace(/\/$/, "") + "/api/v1";

export const documentLanguages = {
  auto: "Mixed English, Hindi and Punjabi",
  en: "English",
  hi: "Hindi / हिन्दी",
  pa: "Punjabi / ਪੰਜਾਬੀ",
};
export type DocumentLanguage = keyof typeof documentLanguages;
export type DocumentKind = { label: string; category: string; evidence_type: string };
export type SavedDocument = DocumentKind & {
  id: string;
  type: string;
  language: DocumentLanguage;
  content_type: string;
  created_at: string;
};

export async function documentRequest<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(documentApi + path, { credentials: "include", cache: "no-store", ...init });
  if (response.status === 204) return undefined as T;
  const result = await response.json();
  if (!response.ok) throw new Error(typeof result.detail === "string" ? result.detail : "The document request failed.");
  return result as T;
}

export function listSavedDocuments(signal?: AbortSignal) {
  return documentRequest<SavedDocument[]>("/saved-documents", { signal });
}
