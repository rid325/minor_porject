"use client";

import { FormEvent, useRef, useState } from "react";
import { chatLabel, type ChatLanguage } from "@/lib/chat-language";
import Link from "next/link";
import { useRouter } from "next/navigation";

const labels: Record<string, string> = {
  "location.state": "State or Union Territory",
  "education.student_status": "Currently studying",
  "agriculture.farmer_status": "Farmer",
  "personal.date_of_birth": "Date of birth",
  "personal.marital_status": "Marital status",
  "household.family_income": "Annual household income (INR)",
};
type Ref = { id: string; name: string; excerpt: string; excerpt_translation?: string; conditional_translation?: string; translation_incomplete?: boolean; conditional?: string; source?: string; checked?: string; assessment?: {category: string; next_condition?: string} };
type Reply = {
  language: ChatLanguage; text: string; session: string; references: Ref[]; facts: Record<string, string>;
  pending: Record<string, string>; changes: {field: string; previous: string; current: string}[];
  model_available?: boolean;
};
type Message = { lang?: ChatLanguage; text: string; refs?: Ref[]; role: "user" | "assistant" };

export default function ChatbotPage() {
  const router = useRouter();
  const [input, setInput] = useState("");
  const [reply, setReply] = useState<Reply>();
  const [messages, setMessages] = useState<Message[]>([]);
  const busyRef = useRef(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const lang: ChatLanguage = /[\u0a00-\u0a7f]/.test(input) ? "pa" : /[\u0900-\u097f]/.test(input) ? "hi" : reply?.language || "en";
  const t = (key: string) => chatLabel(key, lang);
  async function send(message: string, decision?: "confirm" | "dismiss", field?: string, value?: string) {
    if (busyRef.current || (!message.trim() && !decision)) return;
    busyRef.current = true;
    setBusy(true);
    setError("");
    try {
      const response = await fetch("/api/v1/chat", {
        method: "POST", headers: {"Content-Type": "application/json"},
        body: JSON.stringify({message, decision, field, value, session: reply?.session}),
      });
      if (response.status === 410) {
        setReply(undefined);
        throw new Error("This conversation expired. Send your question to start a new one.");
      }
      if (response.status === 503) throw new Error("The chat service is offline. Please retry in a moment.");
      if (response.status === 429) throw new Error("The chat service is receiving too many requests. Please retry shortly.");
      if (!response.ok) throw new Error("Could not complete that turn. Please retry.");
      const data: Reply = await response.json();
      const userMessage: Message = {role: "user", text: decision ? t(decision === "confirm" ? "Confirmed" : "Dismissed") + " · " + t(labels[field!]) + " · " + t(value || "") : message};
      setMessages(current => [...current, userMessage, {role: "assistant", text: data.text, lang: data.language, refs: data.references}]);
      setReply(data);
      if (!decision) setInput("");
    } catch (err) { setError(lang !== "en" ? t("Retry") : err instanceof Error ? err.message : "Could not reach the assistant."); }
    finally { busyRef.current = false; setBusy(false); }
  }
  function openProfile() {
    sessionStorage.setItem("yojana-confirmed-intake", JSON.stringify(reply?.facts || {}));
    router.push("/profile?fromChat=1");
  }
  function submit(event: FormEvent) { event.preventDefault(); void send(input); }
  return <main className="chat-page"><div className="page-wrap page-intro"><h1>{t("Scheme assistant")}</h1>
    <p>{t("Ask about benefits, documents or application steps in English, Hindi or Punjabi. Translations include the original catalogue wording. Leave out identity numbers.")}</p></div>
    <section className="page-wrap chat-shell"><div className="chat-card">
      <div className="chat-messages" aria-live="polite">{messages.map((m,i) => <div className={'chat-message ' + m.role} key={i}><div>{m.text}
        {m.refs?.map(r => <article key={r.id}><h3><Link href={'/schemes/' + encodeURIComponent(r.id)}>{r.name}</Link></h3><p>{r.excerpt_translation || (m.lang === "en" ? r.excerpt : "")}</p>
          {r.conditional && (r.conditional_translation || m.lang === "en") && <p>{chatLabel("Conditional documents", m.lang || "en")} · {r.conditional_translation || r.conditional}</p>}
          {r.translation_incomplete && <p>{chatLabel("Translation unavailable", m.lang || "en")}</p>}
          {m.lang && m.lang !== "en" && <details><summary>{chatLabel("Original wording", m.lang)}</summary><p lang="en">{r.excerpt}</p><p lang="en">{r.conditional}</p></details>}
          {r.assessment && <p>{chatLabel("Preliminary check", m.lang || "en")} · {chatLabel(r.assessment.category,m.lang || "en")}</p>}
          {r.source && <a href={r.source} target="_blank" rel="noreferrer">{chatLabel("Source",m.lang || "en")} {r.checked && " · " + r.checked}</a>}</article>)}</div></div>)}</div>
      {!messages.length && <div className="chat-suggestions">{["I am a farmer from Punjab", "हरियाणा की पेंशन योजनाएँ", "ਪੈਨਸ਼ਨ ਲਈ ਕਿਹੜੇ ਦਸਤਾਵੇਜ਼ ਚਾਹੀਦੇ ਹਨ?"].map(q => <button type="button" disabled={busy} key={q} onClick={() => setInput(q)}>{q}</button>)}</div>}
      {reply?.model_available === false && <p role="status">{t("The local language model is unavailable. Showing keyword search results.")}</p>}
      {busy && <p role="status">{t("Searching the catalogue…")}</p>}{error && <p role="alert">{error}</p>}
      <form className="chat-input-row" onSubmit={submit}><input aria-label={t("Your question")} maxLength={1000} value={input} onChange={e => setInput(e.target.value)} placeholder={t("Your question")}/><button className="btn btn-primary" disabled={busy || !input.trim()}>{t("Send")}</button></form>
    </div><aside className="chat-next"><h2>{t("Your profile details")}</h2><p>{t("Review each suggestion before adding it to your profile.")}</p>
      {Object.entries(reply?.pending || {}).map(([k,v]) => <div key={k}><p>{t(labels[k])} · {t(v)}</p>{(["confirm","dismiss"] as const).map(d => <button className="btn btn-secondary" key={d} disabled={busy} onClick={() => send("", d, k, v)}>{t(d === "confirm" ? "Confirm" : "Dismiss")}</button>)}</div>)}
      {Object.entries(reply?.facts || {}).map(([k,v]) => <p key={k}>{t(labels[k])} · {t(v)}</p>)}
      {reply?.changes.map((h,i) => <small key={i}>{t(labels[h.field])} · {t("Changed")} · {t(h.previous)} → {t(h.current)}. </small>)}
      {Object.keys(reply?.facts || {}).length ? <button className="btn btn-primary" onClick={openProfile}>{t("Use confirmed details in my profile")}</button> : <Link href="/profile">{t("Open profile form")}</Link>}
    </aside></section></main>;
}
