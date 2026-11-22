"use client";

import { FormEvent, useEffect, useState } from "react";
import Link from "next/link";
import { getAuthStatus } from "@/lib/auth";
import {
  documentApi, documentLanguages, documentRequest, listSavedDocuments,
  type DocumentKind, type SavedDocument,
} from "@/lib/documents";

export default function SavedDocuments({ uploadOnly = false }: { uploadOnly?: boolean }) {
  const [types, setTypes] = useState<Record<string, DocumentKind>>({});
  const [documents, setDocuments] = useState<SavedDocument[]>([]);
  const [selectedType, setSelectedType] = useState("");
  const [error, setError] = useState("");
  const [status, setStatus] = useState("");
  const [pending, setPending] = useState(false);
  const [removeId, setRemoveId] = useState<string>();
  const [authenticated, setAuthenticated] = useState<boolean>();
  const [previewFile, setPreviewFile] = useState<File>();
  const [previewUrl, setPreviewUrl] = useState<string>();

  useEffect(() => {
    if (!previewFile) return;
    const url = URL.createObjectURL(previewFile);
    setPreviewUrl(url);
    return () => URL.revokeObjectURL(url);
  }, [previewFile]);

  useEffect(() => {
    const controller = new AbortController();
    getAuthStatus().then(async ({ authenticated: signedIn }) => {
      if (controller.signal.aborted) return;
      setAuthenticated(signedIn);
      if (!signedIn) return;
      const [catalogue, saved] = await Promise.all([
        documentRequest<Record<string, DocumentKind>>("/document-types", { signal: controller.signal }),
        uploadOnly ? Promise.resolve([]) : listSavedDocuments(controller.signal),
      ]);
      if (controller.signal.aborted) return;
      setTypes(catalogue);
      setDocuments(saved);
    }).catch((failure: Error) => {
      if (!controller.signal.aborted) setError(failure.message);
    });
    return () => controller.abort();
  }, [uploadOnly]);

  const groups = Object.entries(types).reduce<Record<string, [string, DocumentKind][]>>((result, entry) => {
    (result[entry[1].category] ??= []).push(entry);
    return result;
  }, {});

  async function save(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const formElement = event.currentTarget;
    const form = new FormData(formElement);
    const file = form.get("file");
    if (!(file instanceof File) || !file.size) return;
    setStatus("");
    setError("");
    if (file.size > 8 * 1024 * 1024) {
      setError("Choose a file up to 8 MB.");
      return;
    }
    setPending(true);
    try {
      const saved = await documentRequest<SavedDocument>(
        "/saved-documents/" + selectedType + "?language=" + String(form.get("language")),
        {
          method: "POST",
          headers: {
            "Content-Type": file.type,
            "X-Document-Consent": String(form.has("consent")),
            "X-Masked-Aadhaar": String(form.has("masked")),
          },
          body: file,
        },
      );
      if (!uploadOnly) setDocuments((current) => [saved, ...current]);
      formElement.reset();
      setPreviewFile(undefined);
      setSelectedType("");
      setStatus("Document saved.");
    } catch (failure) {
      setError(failure instanceof Error ? failure.message : "The document could not be saved.");
    } finally {
      setPending(false);
    }
  }

  async function remove(id: string) {
    setStatus("");
    setError("");
    setPending(true);
    try {
      await documentRequest("/saved-documents/" + id, { method: "DELETE" });
      setDocuments((current) => current.filter((item) => item.id !== id));
      setRemoveId(undefined);
      setStatus("Document deleted.");
    } catch (failure) {
      setError(failure instanceof Error ? failure.message : "The document could not be deleted.");
    } finally {
      setPending(false);
    }
  }

  return (
    <section id="save-documents" className="account-panel document-checker checker-library">
      <h2>{uploadOnly ? "Upload a document" : "Saved documents"}</h2>
      <p>{uploadOnly ? "Add a PDF, PNG, or JPEG to your account for comparison." : "Store and manage your PDF, PNG, and JPEG documents in your account."}</p>
      {authenticated === false && <p><Link href="/login">Sign in</Link> to add or manage saved documents.</p>}
      {authenticated === undefined && !error && <p role="status">Checking sign-in…</p>}
      {authenticated && <form onSubmit={save}>
        <fieldset disabled={pending}>
          <label>Document type
            <select required value={selectedType} onChange={(event) => setSelectedType(event.target.value)}>
              <option value="">Select a document type</option>
              {Object.entries(groups).map(([category, entries]) => (
                <optgroup key={category} label={category}>
                  {entries.map(([code, item]) => <option key={code} value={code}>{item.label}</option>)}
                </optgroup>
              ))}
            </select>
          </label>
          <label>Document language
            <select name="language" defaultValue="en">
              {Object.entries(documentLanguages).map(([code, label]) => <option key={code} value={code}>{label}</option>)}
            </select>
          </label>
          <label>Document file (up to 8 MB)
            <input name="file" type="file" accept="application/pdf,image/png,image/jpeg" required onChange={(event) => {
              const file = event.currentTarget.files?.[0];
              setPreviewFile(file && file.size <= 8 * 1024 * 1024 &&
                ["application/pdf", "image/png", "image/jpeg"].includes(file.type) ? file : undefined);
            }} />
          </label>
          {previewFile && previewUrl && <details className="checker-details">
            <summary>Preview selected document</summary>
            {previewFile.type === "application/pdf"
              ? <iframe className="checker-document-preview" title="PDF preview" src={previewUrl} sandbox="" />
              : <img className="checker-document-preview" src={previewUrl} alt="Selected document preview" />}
          </details>}
          {previewFile && <button type="button" className="btn btn-ghost" onClick={(event) => {
            const input = event.currentTarget.form?.elements.namedItem("file");
            if (input instanceof HTMLInputElement) input.value = "";
            setPreviewFile(undefined);
          }}>Remove selected file</button>}
          {selectedType === "aadhaar" && <label>
            <input name="masked" type="checkbox" required /> This is masked Aadhaar. Only the last four digits are visible.
          </label>}
          <label><input name="consent" type="checkbox" required /> I consent to storing this file in my account.</label>
          <button className="btn btn-primary" type="submit" disabled={!selectedType}>{pending ? "Saving…" : "Add document to account"}</button>
        </fieldset>
      </form>}
      {error && <p role="alert">{error}</p>}
      {status && <p role="status">{status}</p>}
      {!uploadOnly && documents.length > 0 && (
        <ul>
          {documents.map((item) => (
            <li key={item.id}>
              <strong>{item.label}</strong> · {documentLanguages[item.language]} · {new Date(item.created_at).toLocaleDateString("en-IN")}
              <div className="account-actions">
                <a className="btn btn-secondary" href={documentApi + "/saved-documents/" + item.id + "/file"}>Download</a>
                {removeId === item.id ? <>
                  <button className="btn btn-secondary" type="button" disabled={pending} onClick={() => void remove(item.id)}>Confirm deletion</button>
                  <button className="btn btn-ghost" type="button" disabled={pending} onClick={() => setRemoveId(undefined)}>Cancel</button>
                </> : <button className="btn btn-ghost" type="button" disabled={pending} onClick={() => setRemoveId(item.id)}>Delete</button>}
              </div>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}



