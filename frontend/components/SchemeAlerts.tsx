"use client";

import { useEffect, useState, type FormEvent } from "react";
import { documentRequest } from "@/lib/documents";

type AlertSettings = {
  email: string;
  email_verified: boolean;
  email_enabled: boolean;
};
type DemoInbox = {
  has_profile: boolean;
  has_deadlines: boolean;
  messages: { id: string; title: string; text: string; scheme_path: string }[];
};

export default function SchemeAlerts() {
  const [settings, setSettings] = useState<AlertSettings>();
  const [awaitingCode, setAwaitingCode] = useState(false);
  const [code, setCode] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [status, setStatus] = useState("");
  const [demo, setDemo] = useState<DemoInbox>();

  useEffect(() => {
    const controller = new AbortController();
    documentRequest<AlertSettings>("/notifications", { signal: controller.signal }).then((saved) => {
      setSettings(saved);
    }).catch(() => {
      if (!controller.signal.aborted) setError("Alert settings could not load. Refresh to try again.");
    });
    return () => controller.abort();
  }, []);

  async function perform(action: () => Promise<void>) {
    setBusy(true);
    setError("");
    setStatus("");
    try {
      await action();
    } catch (failure) {
      setError(failure instanceof Error ? failure.message : "Unable to update scheme alerts.");
    } finally {
      setBusy(false);
    }
  }

  function sendCode() {
    void perform(async () => {
      await documentRequest("/notifications/verify/email", { method: "POST" });
      setAwaitingCode(true);
      setCode("");
      setStatus("Check your registered email for the verification code.");
    });
  }

  function confirm(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    void perform(async () => {
      const updated = await documentRequest<AlertSettings>("/notifications/verify/email/confirm", {
        method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ code }),
      });
      setSettings(updated);
      setAwaitingCode(false);
      setCode("");
      setStatus("Email verified. You can now turn on email alerts.");
    });
  }

  function toggle(enabled: boolean) {
    if (!settings) return;
    void perform(async () => {
      const updated = await documentRequest<AlertSettings>("/notifications", {
        method: "PUT", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          email_enabled: enabled,
        }),
      });
      setSettings(updated);
      setStatus(enabled ? "Alerts turned on." : "Alerts turned off.");
    });
  }

  return (
    <section id="scheme-alerts" className="account-panel checker-library document-checker">
      <h2>Scheme alerts</h2>
      <p>Get an email when a scheme matches your saved profile or its application deadline is within seven days.</p>
      <h3>Demo email inbox</h3>
      <p>Preview alerts for your saved profile. Demo messages appear here only.</p>
      <button className="btn btn-primary" type="button" disabled={busy} onClick={() => {
        setDemo(undefined);
        void perform(async () => {
          setDemo(await documentRequest<DemoInbox>("/notifications/demo"));
        });
      }}>Run demo check</button>
      {demo && <div aria-live="polite">
        {!demo.has_profile ? <p><a href="/profile">Save your profile</a> to generate demo alerts.</p>
          : demo.messages.length === 0 ? <p>No likely scheme matches for your saved profile yet.</p>
          : <ul>{demo.messages.map((message) => <li key={message.id}>
            <strong>{message.title}</strong>
            <p>{message.text}</p>
            <a href={message.scheme_path}>View scheme</a>
          </li>)}</ul>}
        {!demo.has_deadlines && <p>Deadline reminders appear when confirmed closing dates are configured.</p>}
      </div>}
      {settings && <fieldset disabled={busy}>
        <h3>Email delivery</h3>
        <p>{settings.email}{settings.email_verified && " · Verified"}</p>
        {settings.email_verified ? <label>
          <input type="checkbox" checked={settings.email_enabled} onChange={(event) => toggle(event.target.checked)} /> Send scheme alerts to my registered email
        </label> : <button className="btn btn-secondary" type="button" onClick={sendCode}>Send email verification code</button>}
        {awaitingCode && <form onSubmit={confirm}>
          <label>Email verification code
            <input type="text" inputMode="numeric" autoComplete="one-time-code" pattern="[0-9]{6}" required value={code} onChange={(event) => setCode(event.target.value)} />
          </label>
          <button className="btn btn-primary" type="submit">Verify code</button>
        </form>}
      </fieldset>}
      {error && <p role="alert">{error}</p>}
      {status && <p role="status">{status}</p>}
      {busy && <p role="status">Updating scheme alerts…</p>}
    </section>
  );
}
