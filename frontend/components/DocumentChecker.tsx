"use client";

import Link from "next/link";
import MismatchResolution, { type Guide } from "./MismatchResolution";
import DocumentResolutionExample from "./DocumentResolutionExample";
import { documentApi, documentLanguages, listSavedDocuments, type DocumentLanguage, type SavedDocument } from "@/lib/documents";
import { FormEvent, useEffect, useRef, useState } from "react";

const apiBase = (process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000").replace(/\/$/, "");

const documentTypes = {
  identity: "Identity proof",
  residence: "Residence proof",
  age: "Age proof",
  bank: "Bank account evidence",
  income: "Income certificate",
  family_id: "Parivar Pehchan Patra / Family ID",
  category: "Caste or category certificate",
  disability: "Disability evidence",
  other: "Other supporting evidence",
  unknown: "Choose an evidence type",
};

const fields = {
  name: { label: "Applicant or account holder name", type: "text" },
  father_name: { label: "Father’s name", type: "text" },
  mother_name: { label: "Mother’s name", type: "text" },
  date_of_birth: { label: "Date of birth", type: "date" },
  gender: { label: "Gender", type: "text" },
  place_of_birth: { label: "Place of birth", type: "text" },
  address: { label: "Address", type: "text" },
  house_number: { label: "House number", type: "text" },
  street: { label: "Street", type: "text" },
  sector: { label: "Sector", type: "text" },
  village: { label: "Village", type: "text" },
  city: { label: "City", type: "text" },
  state: { label: "State", type: "text" },
  district: { label: "District", type: "text" },
  social_category: { label: "Social category", type: "text" },
  disability_percentage: { label: "Disability percentage", type: "number" },
  pin: { label: "Postal PIN", type: "text" },
  annual_household_income: { label: "Annual household income in INR", type: "number" },
};

type DocumentType = keyof typeof documentTypes;
type Field = keyof typeof fields;
type ExtractedField = {
  value: string;
  original_value?: string;
  date_format_uncertain?: boolean;
  page: number;
  bounding_box: [number, number, number, number] | null;
  ocr_confidence: number | null;
};
type Extraction = {
  fields: Partial<Record<Field, ExtractedField>>;
  display_values?: Partial<Record<Field, string>>;
  field_languages?: Partial<Record<Field, string | null>>;
  document_details?: { issued_on?: string; issuing_authority?: string; document_number?: string };
  expires_on: string | null;
  page_count: number;
  recognized_text_pages?: number;
  unreadable_pages: number[];
  ambiguous_fields: (Field | "expires_on")[];
};
type DocumentRow = { id: number; type: DocumentType; language: DocumentLanguage; pendingFile?: File; saved?: SavedDocument; manual?: boolean; upload?: Extraction; revision?: number };
type Checklist = { version: string; required_types: DocumentType[] };
type Evidence = {
  document: number;
  field: Field;
  page: number;
  ocr_confidence: number | null;
  extraction_confidence: number | null;
  language?: string | null;
  confidence_band?: string | null;
};
const comparisonLabels: Record<string, string> = {
  exact_match: "Exact match",
  normalized_match: "Normalized match",
  language_variation: "Language variation",
  transliteration_match: "Transliteration match",
  possible_match: "Possible match",
  spelling_mismatch: "Possible spelling mismatch",
  actual_mismatch: "Mismatch",
  needs_verification: "Needs verification",
  clear_mismatch: "Mismatch",
  possible_mismatch: "Possible mismatch",
  likely_match: "Possible match",
};
const comparisonNotes: Record<string, string> = {
  language_variation: "These values appear equivalent across scripts. Check the originals before requesting a correction.",
  transliteration_match: "These values have the same transliteration. Verify the original spelling if it matters for your application.",
  needs_verification: "Check the original values or the dates of the records before treating this as a discrepancy.",
  possible_match: "A spelling, initial, or omitted name may explain the difference. Confirm the complete value on each original.",
  spelling_mismatch: "A spelling or reading error may explain this difference. Verify both originals before requesting a correction.",
  actual_mismatch: "The values differ after normalization. Establish the correct value using supporting evidence.",
};
type Report = {
  checklist_version: string | null;
  rule_set_version: string | null;
  document_count: number;
  fields_checked: number;
  comparisons: { status: string; classification?: string; comparison: string; evidence: Evidence[] }[];
  findings: {
    code: string;
    severity: "blocker" | "warning" | "information";
    message: string;
    action: string;
    document: number | null;
    evidence: Evidence[];
    source_url: string | null;
  }[];
};

const personalFields: Field[] = ["name", "father_name", "mother_name", "date_of_birth", "gender", "place_of_birth"];
const addressFields: Field[] = ["address", "house_number", "street", "sector", "village", "city", "state", "district", "pin"];
const relevantFields: Record<DocumentType, Field[]> = {
  identity: [...personalFields, ...addressFields],
  residence: ["name", ...addressFields],
  age: [...personalFields, ...addressFields],
  bank: ["name"],
  income: ["name", "annual_household_income"],
  family_id: [...personalFields, ...addressFields],
  category: ["name", "social_category"],
  disability: ["name", "disability_percentage"],
  other: [...personalFields, ...addressFields],
  unknown: [],
};

export default function DocumentChecker({ schemeId, savedOnly = false }: { schemeId?: string; savedOnly?: boolean }) {
  const endpoint = apiBase + "/api/v1" + (schemeId ? "/schemes/" + encodeURIComponent(schemeId) : "");
  const [checklist, setChecklist] = useState<Checklist>();
  const [documents, setDocuments] = useState<DocumentRow[]>(() => Array.from(
    { length: savedOnly ? 2 : schemeId ? 0 : 1 },
    (_, id) => ({ id, type: "unknown", language: "en" }),
  ));
  const nextId = useRef(documents.length);
  const [savedDocuments, setSavedDocuments] = useState<SavedDocument[]>();
  const [savedError, setSavedError] = useState(false);
  const [report, setReport] = useState<Report>();
  const [guides, setGuides] = useState<Record<string, Guide>>({});
  const [submittedValues, setSubmittedValues] = useState<Record<Field, string>[]>([]);
  const [submittedRows, setSubmittedRows] = useState<DocumentRow[]>([]);
  const [readErrorId, setReadErrorId] = useState<number>();
  const [error, setError] = useState("");
  const [signInRequired, setSignInRequired] = useState(false);
  const [pending, setPending] = useState(false);
  const [consent, setConsent] = useState(false);
  const [useCloudOcr, setUseCloudOcr] = useState(false);
  const [uploading, setUploading] = useState<number>();
  const reportHeading = useRef<HTMLHeadingElement>(null);

  useEffect(() => {
    if (!savedOnly) return;
    const controller = new AbortController();
    listSavedDocuments(controller.signal).then((items) => {
      if (!controller.signal.aborted) setSavedDocuments(items);
    }).catch(() => {
      if (!controller.signal.aborted) setSavedError(true);
    });
    return () => controller.abort();
  }, [savedOnly]);

  useEffect(() => {
    if (!report) return;
    reportHeading.current?.focus();
  }, [report]);

  useEffect(() => {
    const controller = new AbortController();
    if (schemeId) fetch(endpoint + "/document-checklist", { signal: controller.signal, cache: "no-store" })
      .then((response) => response.ok ? response.json() : undefined)
      .then(setChecklist)
      .catch(() => {});
    return () => controller.abort();
  }, [endpoint, schemeId]);

  if (schemeId && !checklist) return null;

  async function readDocument(row: DocumentRow) {
    const file = row.pendingFile;
    if (!file && !row.saved) return false;
    setError("");
    setReadErrorId(row.id);
    setSignInRequired(false);
    if (file && file.size > 8 * 1024 * 1024) {
      setError("Upload a file up to 8 MB.");
      return false;
    }
    if (!consent || row.type === "unknown") {
      setError("Choose an evidence type before reading the document.");
      return false;
    }
    setUploading(row.id);
    setReport(undefined);
    try {
      const path = row.saved
        ? "/saved-document-extractions/" + encodeURIComponent(row.saved.id) + "/" + row.type
        : "/document-extractions/" + row.type;
      const response = await fetch(endpoint + path + "?language=" + row.language, {
        method: "POST",
        credentials: "include",
        headers: {
          ...(file && { "Content-Type": file.type || (file.name.toLowerCase().endsWith(".pdf") ? "application/pdf" : file.name.toLowerCase().endsWith(".png") ? "image/png" : "image/jpeg") }),
          "X-Document-Consent": "true",
          ...(useCloudOcr ? { "X-Cloud-OCR-Consent": "true" } : {}),
        },
        body: file,
      });
      if (response.status === 401) {
        setSignInRequired(true);
        return false;
      }
      const result = await response.json().catch(() => ({}));
      if (!response.ok) {
        throw new Error(typeof result.detail === "string" ? result.detail : "The file could not be read.");
      }
      setReadErrorId(undefined);
      setDocuments((previous) => previous.map((item) => item.id === row.id ? {
        ...item, upload: result as Extraction, revision: (item.revision ?? 0) + 1,
      } : item));
      return result as Extraction;
    } catch (failure) {
      setError(failure instanceof Error ? failure.message : "The upload is unavailable.");
      return false;
    }
  }

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (busy || !canCompare) return;
    setReport(undefined);
    setGuides({});
    setSubmittedValues([]);
    setSubmittedRows([]);
    const form = new FormData(event.currentTarget);
    setError("");
    setSignInRequired(false);
    if (!consent) {
      setError("Give consent before reading or checking documents.");
      return;
    }
    const freshUploads = new Map<number, Extraction>();
    if (unreadRows.length) {
      try {
        for (const row of unreadRows) {
          const extraction = await readDocument(row);
          if (!extraction) return;
          freshUploads.set(row.id, extraction);
        }
      } finally {
        setUploading(undefined);
      }
    }
    const selectedRows = documents.filter((row) => row.type !== "unknown")
      .map((row) => ({ ...row, upload: freshUploads.get(row.id) ?? row.upload }));
    const payload = selectedRows.map(({ id, type, upload }) => {
      const fresh = freshUploads.get(id);
      const values = relevantFields[type].flatMap((field) => {
        const value = (fresh ? fresh.fields[field]?.value ?? "" : String(form.get(id + "-" + field) ?? "")).trim();
        const page = fresh ? fresh.fields[field]?.page : Number(form.get(id + "-" + field + "-page"));
        if (!value || page === undefined) return [];
        const original = upload?.fields[field];
        const unchanged = original && (original.value === value || upload?.display_values?.[field] === value);
        const provenance = unchanged && original.page === page
          ? { bounding_box: original.bounding_box, ocr_confidence: original.ocr_confidence, original_value: original.original_value,
              date_format_uncertain: original.date_format_uncertain }
          : {};
        return [[field, { value: unchanged ? original.value : value, page, ...provenance, user_confirmed: form.has(id + "-reviewed") }] as const];
      });
      return {
        document_type: type,
        expires_on: fresh ? fresh.expires_on : form.get(id + "-expiry") || null,
        issued_on: upload?.document_details?.issued_on ?? null,
        readable: fresh ? fresh.unreadable_pages.length < fresh.page_count : !form.has(id + "-unreadable"),
        missing_pages: form.has(id + "-missing"),
        fields: Object.fromEntries(values),
      };
    });
    if (payload.some((item) => Object.values(item.fields).some((field) => !Number.isInteger(field.page) || field.page < 1 || field.page > 500))) {
      setError("Check that each supplied field has a valid page number.");
      return;
    }
    setPending(true);
    try {
      const response = await fetch(endpoint + "/document-checks", {
        method: "POST",
        credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ consent: form.has("document-consent"), documents: payload, compare_unconfirmed: !schemeId }),
      });
      if (response.status === 401) {
        setSignInRequired(true);
        return;
      }
      if (!response.ok) {
        throw new Error(response.status === 422 ? "Check your evidence fields and try again." : "The document check is unavailable. Try again later.");
      }
      const result: Report = await response.json();
      setSubmittedValues(payload.map((item) => Object.fromEntries(
        Object.entries(item.fields).map(([field, evidence]) => [field, evidence.value]),
      ) as Record<Field, string>));
      setSubmittedRows(selectedRows);
      setReport(result);
    } catch (failure) {
      setError(failure instanceof Error ? failure.message : "The document check is unavailable.");
    } finally {
      setPending(false);
    }
  }

  function resolutionFor(evidence: Evidence[]) {
    if (!evidence.length || evidence.length > 2 || (evidence.length === 2 && evidence[0].field !== evidence[1].field)) return null;
    function compared(item: Evidence) {
      const row = submittedRows[item.document - 1];
      const value = submittedValues[item.document - 1]?.[item.field];
      if (!row || !value) return undefined;
      return { kind: row.saved?.type ?? "role_" + row.type, label: row.saved?.label ?? documentTypes[row.type],
        number: item.document, value, page: item.page, confidence: item.ocr_confidence,
        displayValue: row.upload?.fields[item.field]?.value === value ? row.upload?.display_values?.[item.field] : undefined };
    }
    const first = compared(evidence[0]);
    const second = evidence.length === 2 ? compared(evidence[1]) : {
      kind: "role_profile", label: "Saved profile", value: "Saved profile", page: 0, number: 0,
    };
    const field = evidence[0].field;
    const key = evidence.map((item) => item.document + "-" + item.field).join(":");
    return first && second ? <MismatchResolution schemeId={schemeId} field={field} fieldLabel={fields[field].label} pair={[first, second]}
      onGuide={(guide) => setGuides((current) => ({ ...current, [key]: guide }))} /> : null;
  }

  const unreadRows = documents.filter((row) => !row.manual && !row.upload && (row.pendingFile || row.saved));
  const canCompare = savedOnly ? documents.length >= 2 && documents.every((row) => row.saved && row.type !== "unknown")
    : Boolean(schemeId || unreadRows.length || documents.some((row) => row.type !== "unknown"));
  const busy = pending || uploading !== undefined;
  const comparisons = report?.comparisons ?? [];
  const classification = (item: Report["comparisons"][number]) => item.classification ?? item.status;
  const count = (...states: string[]) => comparisons.filter((item) => states.includes(classification(item))).length;
  const matches = count("exact_match", "normalized_match");
  const differences = count("actual_mismatch", "clear_mismatch", "spelling_mismatch", "possible_mismatch");
  const review = count("possible_match", "likely_match", "needs_verification");
  const variations = count("language_variation", "transliteration_match");
  const missing = (Object.keys(fields) as Field[]).flatMap((field) => {
    const applicable = submittedRows.map((row, index) => ({ row, index }))
      .filter(({ row }) => relevantFields[row.type].includes(field));
    if (applicable.length < 2 || !applicable.some(({ index }) => submittedValues[index]?.[field])) return [];
    return applicable.filter(({ index }) => !submittedValues[index]?.[field]).map(({ row, index }) =>
      fields[field].label + " missing from " + (row.saved?.label ?? "Document " + (index + 1)));
  });

  function downloadReport() {
    if (!report) return;
    const sections = ["Yojna Connect document comparison", "",
      `${report.document_count} documents | ${comparisons.length} comparisons | ${matches} matches | ${differences} discrepancies | ${variations} language variations | ${review} need verification | ${missing.length} missing values`, ""];
    submittedRows.forEach((row, index) => {
      sections.push(`Document ${index + 1}: ${row.saved?.label ?? row.pendingFile?.name ?? documentTypes[row.type]}`);
      const details = row.upload?.document_details;
      if (details?.issued_on) sections.push("Issue date: " + details.issued_on);
      if (details?.issuing_authority) sections.push("Issuing authority: " + details.issuing_authority);
      if (details?.document_number) sections.push("Document number: " + details.document_number);
      if (row.upload?.expires_on) sections.push("Expiry date: " + row.upload.expires_on);
      for (const [field, value] of Object.entries(submittedValues[index] ?? {}) as [Field, string][]) {
        const extracted = row.upload?.fields[field];
        const original = extracted?.value === value ? extracted.original_value ?? value : value;
        const details = extracted?.value === value ? [
          row.upload?.field_languages?.[field],
          extracted.ocr_confidence == null ? undefined : `OCR confidence ${Math.round(extracted.ocr_confidence * 100)}%`,
          extracted.date_format_uncertain ? "date format needs verification" : undefined,
        ].filter(Boolean) : [];
        sections.push(`- ${fields[field].label}: ${original}${details.length ? " (" + details.join("; ") + ")" : ""}`);
      }
    });
    sections.push("", "Field-by-field comparisons");
    comparisons.forEach((item) => sections.push(
      `- ${fields[item.evidence[0].field].label}, ${item.evidence.map((evidence) => "document " + evidence.document).join(" and ")}${item.comparison === "profile_comparison" ? " and saved profile" : ""}: ${comparisonLabels[classification(item)] ?? classification(item)}`,
    ));
    if (missing.length) sections.push("", "Missing values", ...missing);
    if (report.findings.length) sections.push("", "Findings", ...report.findings.map((item) => item.message + " " + item.action));
    const priorityOrder: Record<string, number> = { High: 0, Medium: 1, Low: 2 };
    const orderedGuides = Object.entries(guides).sort(([, first], [, second]) =>
      (priorityOrder[first.priority ?? ""] ?? 3) - (priorityOrder[second.priority ?? ""] ?? 3));
    for (const [key, guide] of orderedGuides) {
      const [document, field] = key.split(":")[0].split("-") as [string, Field];
      sections.push("", `Correction guidance for ${fields[field].label} (document ${document})`,
        guide.first_action, guide.priority ? "Priority: " + guide.priority : "", guide.explanation,
        guide.impact, ...(guide.possible_reasons ?? []), guide.correction, guide.why);
      for (const route of guide.routes) {
        sections.push(route.title, route.online_offline, route.where, ...route.mandatory, ...route.conditional,
          ...route.steps.map((step, index) => (index + 1) + ". " + step), route.fees_timing,
          ...route.sources.map(([label, url]) => label + ": " + url));
      }
      sections.push(...guide.follow_ups, ...guide.next_steps);
    }
    const masked = sections.join("\n")
      .replace(/\b\d{4}[ -]?\d{4}[ -]?\d{4}\b/g, (number) => "XXXX XXXX " + number.slice(-4))
      .replace(/\b[A-Z]{5}\d{4}[A-Z]\b/gi, "XXXXX0000X");
    const url = URL.createObjectURL(new Blob([masked], { type: "text/plain;charset=utf-8" }));
    const link = document.createElement("a");
    link.href = url;
    link.download = "yojna-document-comparison.txt";
    link.click();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  }

  return (
    <section className="document-checker checker-workspace">
      {busy && (
        <div className="checker-loading-overlay" role="status">
          <div className="checker-loading-card">
            <span className="checker-spinner" aria-hidden="true" />
            <span>{pending ? "Normalizing and comparing fields…" : `Extracting text from document ${documents.findIndex((row) => row.id === uploading) + 1} of ${documents.length}…`}</span>
          </div>
        </div>
      )}
      <div className="checker-toolbar">
        <div>
          <h2>{schemeId ? "Application document checker" : "Documents to check"}</h2>
          <p>Choose documents and a reader, then compare the extracted details.</p>
        </div>
      </div>
      {checklist && (
        <div className="checker-checklist">
          <h3>Required evidence</h3>
          <ul>{checklist.required_types.map((type) => <li key={type}>{documentTypes[type]}</li>)}</ul>
        </div>
      )}
      {savedOnly && savedError && <p role="alert">Could not load saved documents. <Link href="/login">Sign in</Link> and reopen Check mismatch.</p>}
      {savedOnly && !savedError && !savedDocuments && <p role="status">Loading saved documents…</p>}
      {savedOnly && savedDocuments && savedDocuments.length < 2 && <p>Use Upload document to add at least two files to your account.</p>}
      <form aria-busy={busy} noValidate onSubmit={submit} onChange={() => setReport(undefined)}>
        <fieldset disabled={busy}>
          {documents.map((row, index) => {
            const { id, type, language, pendingFile, saved } = row;
            return (
            <fieldset className="checker-document" key={id}>
              <legend>Document {index + 1}</legend>
              {savedOnly ? <label>Select document {index + 1}
                <select value={saved?.id ?? ""} disabled={!savedDocuments?.length} onChange={(event) => {
                  const selected = savedDocuments?.find((item) => item.id === event.target.value);
                  setDocuments((previous) => previous.map((item) => item.id !== id ? item : {
                    id, saved: selected, type: (selected?.evidence_type ?? "unknown") as DocumentType,
                    language: selected?.language ?? "en", revision: (item.revision ?? 0) + 1,
                  }));
                  setError("");
                  setReadErrorId(undefined);
                  setSignInRequired(false);
                }}>
                  <option value="">Choose a saved document</option>
                  {savedDocuments?.filter((item) => !documents.some((other) => other.id !== id && other.saved?.id === item.id)).map((item) => (
                    <option key={item.id} value={item.id}>{item.label} · {new Date(item.created_at).toLocaleString("en-IN")}</option>
                  ))}
                </select>
              </label> : <label className="document-upload">Upload a document
                <small>PDF, PNG, or JPEG. Up to 8 MB and five PDF pages.</small>
                <input type="file" accept="application/pdf,image/png,image/jpeg" onChange={(event) => {
                  const file = event.currentTarget.files?.[0];
                  event.currentTarget.value = "";
                  if (!file) return;
                  setError("");
                  setDocuments((previous) => previous.map((item) => item.id === id ? {
                    ...item, pendingFile: file, manual: false, upload: undefined, revision: (item.revision ?? 0) + 1,
                  } : item));
                }} />
              </label>}
              {pendingFile && <p className="checker-file-name"><strong>{pendingFile.name}</strong>{" "}
                <button className="btn btn-ghost" type="button" onClick={() => {
                  setDocuments((previous) => previous.map((item) => item.id === id ? { ...item, pendingFile: undefined, upload: undefined, revision: (item.revision ?? 0) + 1 } : item));
                  setError("");
                }}>Clear file</button>
              </p>}
              {!savedOnly && <div className="checker-options">
              <label>Evidence type
                <select value={type} onChange={(event) => {
                  const selected = event.target.value as DocumentType;
                  setDocuments((previous) => previous.map((item) => item.id === id ? { ...item, type: selected, upload: undefined, revision: (item.revision ?? 0) + 1 } : item));
                }}>
                  {Object.entries(documentTypes).map(([value, label]) => <option key={value} value={value}>{label}</option>)}
                </select>
              </label>
              <label>Document language
                <select value={language} onChange={(event) => {
                  const choice = event.target.value as DocumentLanguage;
                  setDocuments((previous) => previous.map((item) => item.id === id ? { ...item, language: choice, upload: undefined, revision: (item.revision ?? 0) + 1 } : item));
                }}>
                  {Object.entries(documentLanguages).map(([code, label]) => <option key={code} value={code}>{label}</option>)}
                </select>
              </label>
              </div>}
              {readErrorId === id && (pendingFile || saved) && (
                <button className="btn btn-secondary" type="button" onClick={() => {
                  setDocuments((previous) => previous.map((item) => item.id === id ? {
                    ...item, pendingFile: undefined, manual: true,
                  } : item));
                  setError("");
                  setReadErrorId(undefined);
                  document.getElementById("checker-details-" + id)?.setAttribute("open", "");
                }}>Enter details instead</button>
              )}
              {(!savedOnly || documents.length > 2) && <button className="btn btn-ghost checker-remove" type="button" onClick={() => {
                setDocuments((previous) => previous.filter((item) => item.id !== id));
                setReport(undefined);
              }}>Remove document {index + 1}</button>}
            </fieldset>
            );
          })}
          {documents.some((row) => row.type !== "unknown") && (
            <section className="checker-details" aria-label="Optional field corrections">
              <h3>Review or enter details</h3>
              {documents.map(({ id, type, upload, revision, saved }, index) => type !== "unknown" && (
              <details className="checker-details" id={"checker-details-" + id} key={id + "-" + (revision ?? 0)}>
                <summary>{ "Document " + (index + 1) }</summary>
                {saved && <a href={documentApi + "/saved-documents/" + encodeURIComponent(saved.id) + "/file"}>Download original</a>}
                <p>Leave identity and account numbers out of these fields.</p>
                {upload && (
                  <div role="status">
                    {upload.document_details && Object.keys(upload.document_details).length > 0 && (
                      <dl className="resolution-values">
                        {upload.document_details.issuing_authority && <div><dt>Issuing authority</dt><dd>{upload.document_details.issuing_authority}</dd></div>}
                        {upload.document_details.issued_on && <div><dt>Issue date</dt><dd>{upload.document_details.issued_on}</dd></div>}
                        {upload.document_details.document_number && <div><dt>Masked document number</dt><dd>{upload.document_details.document_number}</dd></div>}
                      </dl>
                    )}
                    <p>{Object.keys(upload.fields).length ? Object.keys(upload.fields).length + " fields found. Review the English values against the original before confirming them." : upload.recognized_text_pages ? "Text was readable, but no supported fields were recognized. Check the evidence type or enter the fields below." : "No readable text was found. Try a clearer scan or choose a different document language."}</p>
                    {Object.keys(upload.fields).length > 0 && relevantFields[type].includes("date_of_birth") && !upload.fields.date_of_birth && <p>No date of birth was recognized. Enter it only if the document shows one.</p>}
                    {upload.unreadable_pages.length > 0 && <p>Unreadable pages: {upload.unreadable_pages.join(", ")}.</p>}
                    {upload.ambiguous_fields.length > 0 && <p>Conflicting values on this file need manual entry: {upload.ambiguous_fields.map((field) => field === "expires_on" ? "Expiry date" : fields[field].label).join(", ")}.</p>}

                  </div>
                )}
                {relevantFields[type].map((field) => (
                  <div className="document-checker-field" key={type + field}>
                    <label>{fields[field].label}
                      <input name={id + "-" + field} type={fields[field].type} defaultValue={upload?.display_values?.[field] ?? upload?.fields[field]?.value} maxLength={120} min={field === "annual_household_income" ? 0 : undefined} step="any" />
                    </label>
                    <label>Page
                      <input aria-label={fields[field].label + " page"} name={id + "-" + field + "-page"} type="number" min={1} max={upload?.page_count ?? 500} defaultValue={upload?.fields[field]?.page ?? 1} required />
                    </label>
                  </div>
                ))}
                <label>Expiry date, if applicable<input name={id + "-expiry"} type="date" defaultValue={upload?.expires_on ?? ""} /></label>
                <label><input name={id + "-unreadable"} type="checkbox" defaultChecked={Boolean(upload && upload.unreadable_pages.length === upload.page_count)} /> Entire document unreadable</label>
                <label><input name={id + "-missing"} type="checkbox" /> Missing pages</label>
                {upload && Object.keys(upload.fields).length > 0 && <label><input name={id + "-reviewed"} type="checkbox" required /> I checked these details and page numbers against the original document.</label>}
              </details>
              ))}
            </section>
          )}
          <label className="checker-consent">
            <input name="document-consent" type="checkbox" required checked={consent} onChange={(event) => setConsent(event.target.checked)} />
            <span>I consent to processing these documents and details for this check.</span>
          </label>
          <label>
            Document reader
            <select value={useCloudOcr ? "cloud" : "local"} onChange={(event) => {
              setUseCloudOcr(event.target.value === "cloud");
              setDocuments((previous) => previous.map((row) => row.upload
                ? { ...row, upload: undefined, revision: (row.revision ?? 0) + 1 }
                : row));
            }}>
              <option value="local">Local OCR</option>
              <option value="cloud">Cloud OCR (OCR.space Engine 3)</option>
            </select>
          </label>
          {useCloudOcr && <p>Comparing sends images of the selected document pages to OCR.space.</p>}
          {signInRequired && <p className="checker-notice" role="alert"><Link href="/login">Sign in</Link> to read files and run the document check.</p>}
          {error && <p className="checker-notice" role="alert">{error}</p>}
          <div className="checker-actions">
          <button className="btn btn-secondary" type="button"
            disabled={documents.length >= (savedOnly ? Math.min(savedDocuments?.length ?? 0, 20) : 20)}
            onClick={() => {
            const id = nextId.current++;
            setDocuments((previous) => [...previous, { id, type: "unknown", language: "en" }]);
            setReport(undefined);
          }}>Add another document</button>

          <button className="btn btn-primary" type="submit" disabled={!canCompare}>{uploading !== undefined ? "Reading document…" : pending ? "Checking…" : "Compare documents"}</button>
          </div>
        </fieldset>
      </form>


      {!busy && report && (
        <div className="checker-report" aria-live="polite">
          <h3 ref={reportHeading} tabIndex={-1} id="document-check-results">Comparison results</h3>
          <button type="button" className="btn btn-secondary" onClick={downloadReport}>Download report</button>
          <p>{report.checklist_version && <>Checklist {report.checklist_version} · </>}{report.document_count} documents · {report.fields_checked} fields reviewed</p>
          <dl className="resolution-values">
            {Object.entries({ Comparisons: comparisons.length, Matches: matches, "Language variations": variations,
              Discrepancies: differences, "Needs review": review, "Missing values": missing.length }).map(([label, value]) => (
              <div key={label}><dt>{label}</dt><dd>{value}</dd></div>
            ))}
          </dl>
          {missing.length > 0 && <details className="checker-details">
            <summary>See missing values</summary>
            <ul>{missing.map((item, index) => <li key={index}>{item}</li>)}</ul>
          </details>}
          {report.rule_set_version && <p>Eligibility rules {report.rule_set_version}</p>}
          <p className="checker-result-summary">
            {differences > 0
              ? "Discrepancies found. Review the differences below."
              : review > 0
                ? "Some fields need verification against the original documents."
                : report.comparisons?.length
                  ? "No discrepancies found in the fields compared."
                  : "No comparable fields found. Review or enter details and compare again."}
          </p>
          {submittedRows.some((row) => row.upload) && <p>Check the extracted values against the originals before requesting a correction.</p>}
          {comparisons.map((comparison, index) => (
            <section className="checker-findings" key={index}>
              <h4>{fields[comparison.evidence[0].field].label}</h4>
              <div className="checker-comparison-values">
                {comparison.evidence.map(({ document, field, page, language, confidence_band }) => {
                  const row = submittedRows[document - 1];
                  const value = submittedValues[document - 1]?.[field];
                  const extracted = row?.upload?.fields[field];
                  const display = extracted?.value === value ? row?.upload?.display_values?.[field] ?? value : value;
                  const original = extracted?.value === value ? extracted?.original_value : undefined;
                  return <div key={document}>
                    <strong>{row?.saved?.label ?? ("Document " + document)}</strong>
                    <div>{display}</div>
                    {original && original !== display && <div>Original: {original}</div>}
                    <small>Page {page}{language && " · " + language}{confidence_band && " · " + confidence_band + " OCR confidence"}</small>
                  </div>;
                })}
                {comparison.comparison === "profile_comparison" && <div>Saved profile</div>}
              </div>
              <p><strong>{comparisonLabels[classification(comparison)] ?? comparison.status}</strong></p>
              {comparisonNotes[classification(comparison)] && <p>{comparisonNotes[classification(comparison)]}</p>}
              {classification(comparison) === "needs_verification" && comparison.evidence.map(({ document }) => {
                const id = submittedRows[document - 1]?.id;
                return id === undefined ? null : <a key={document} className="btn btn-ghost" href={"#checker-details-" + id}
                  onClick={() => window.document.getElementById("checker-details-" + id)?.setAttribute("open", "")}>Review document {document}</a>;
              })}
              {["actual_mismatch", "spelling_mismatch", "possible_match", "clear_mismatch", "possible_mismatch"].includes(classification(comparison)) && resolutionFor(comparison.evidence)}
            </section>
          ))}
          {(["blocker", "warning", "information"] as const).map((severity) => {
            const issues = report.findings.filter((finding) => finding.severity === severity);
            if (!issues.length) return null;
            return (
              <section className={"checker-findings checker-findings-" + severity} key={severity}>
                <h4>{{ blocker: "Blockers", warning: "Warnings", information: "Information" }[severity]} <span>{issues.length}</span></h4>
                <ul>{issues.map((finding, index) => (
                  <li key={index}>
                    <strong>{finding.document && "Document " + finding.document + " · "}{finding.message}</strong>
                    <div>{finding.action}</div>
                    {finding.evidence.map((item) => (
                      <div key={item.document + "-" + item.field}>
                        Document {item.document} · Page {item.page} · {fields[item.field].label}
                        {item.ocr_confidence !== null && " · OCR " + Math.round(item.ocr_confidence * 100) + "%"}
                        {item.extraction_confidence !== null && " · Extraction " + Math.round(item.extraction_confidence * 100) + "%"}
                      </div>
                    ))}
                    {finding.source_url && <a href={finding.source_url} target="_blank" rel="noreferrer">Scheme rule source</a>}
                  </li>
                ))}</ul>
              </section>
            );
          })}
        </div>
      )}
      <div className="checker-example"><DocumentResolutionExample schemeId={schemeId} /></div>
    </section>
  );
}











