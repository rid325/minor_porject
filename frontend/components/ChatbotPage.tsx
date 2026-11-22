"use client";

import Link from "next/link";
import { FormEvent, useState } from "react";

type Message = { role: "assistant" | "user"; text: string };

const suggestions = [
  "I am a farmer from Punjab",
  "What documents do I need?",
  "Show me pension schemes",
];

function replyFor(message: string) {
  const value = message.toLowerCase();
  if (value.includes("farmer") || value.includes("kisan")) {
    return "I can help you check agriculture and income-support schemes. Tell me your state, whether you own or lease land, and your approximate annual household income.";
  }
  if (value.includes("document")) {
    return "Documents depend on the scheme. Common examples include identity or residence proof, income or category certificates, bank details and land records. Open a scheme detail page to see its researched document list.";
  }
  if (value.includes("pension")) {
    return "I can help narrow pension schemes by state, age, income and social situation. Start the profile so the eligibility checks can use your answers.";
  }
  return "I can help you find relevant government schemes. Tell me your state, age group, work situation or the kind of support you need. For a structured match, you can also complete your profile.";
}

export default function ChatbotPage() {
  const [messages, setMessages] = useState<Message[]>([
    { role: "assistant", text: "Hello! I’m the Yojna Connect assistant. Tell me a little about your situation and I’ll help you find where to start." },
  ]);
  const [input, setInput] = useState("");

  const send = (event?: FormEvent) => {
    event?.preventDefault();
    const message = input.trim();
    if (!message) return;
    setMessages((current) => [...current, { role: "user", text: message }, { role: "assistant", text: replyFor(message) }]);
    setInput("");
  };

  return (
    <main className="chat-page">
      <div className="page-wrap page-intro chat-intro">
        <span className="eyebrow">Yojna Connect assistant</span>
        <h1>Start with a simple question.</h1>
        <p>Describe your situation in ordinary language. This assistant is a prototype conversation layer; confirm important details through the scheme source and official department.</p>
      </div>
      <section className="page-wrap chat-shell" aria-label="Scheme assistant">
        <div className="chat-card">
          <div className="chat-card-head"><div><strong>Ask about schemes</strong><span>General guidance · no account required</span></div><span className="chat-status"><i /> Online</span></div>
          <div className="chat-messages" aria-live="polite">
            {messages.map((message, index) => <div className={`chat-message ${message.role}`} key={`${message.role}-${index}`}><span>{message.text}</span></div>)}
          </div>
          <div className="chat-suggestions">{suggestions.map((suggestion) => <button type="button" key={suggestion} onClick={() => { setInput(suggestion); }}>{suggestion}</button>)}</div>
          <form className="chat-input-row" onSubmit={send}><input value={input} onChange={(event) => setInput(event.target.value)} placeholder="For example: I am a student from Haryana" aria-label="Message the assistant" /><button className="btn btn-primary" type="submit">Send <span aria-hidden="true">↗</span></button></form>
        </div>
        <aside className="chat-next"><span className="eyebrow">Next step</span><h2>Want an explained shortlist?</h2><p>Complete the structured profile so the deterministic eligibility engine can compare your answers with reviewed scheme rules.</p><Link className="btn btn-secondary" href="/profile">Build my profile <span aria-hidden="true">→</span></Link></aside>
      </section>
    </main>
  );
}
