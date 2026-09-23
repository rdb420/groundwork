import { useState } from "react";
import { api } from "../lib/api";
import { Mark } from "../components/Shell";

export default function Login() {
  const [email, setEmail] = useState("");
  const [state, setState] = useState<"idle" | "sending" | "sent" | "error">("idle");
  const [msg, setMsg] = useState("");
  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setState("sending");
    try {
      await api.send("POST", "/api/auth/request", { email });
      setState("sent");
    } catch (err) {
      setMsg((err as Error).message);
      setState("error");
    }
  };
  return (
    <div className="login">
      <section className="login-story">
        <div className="brand big"><Mark /> Groundwork</div>
        <h1>Show us how the work really gets done.</h1>
        <p>
          The official procedure is one version. The spreadsheet you keep on the side, the email you forward every
          Monday and the photo on your phone are the other. Share them here so the business can be mapped as it
          actually runs, before anything gets built.
        </p>
        <FlowSketch />
      </section>
      <section className="login-form">
        {state === "sent" ? (
          <div className="sent" role="status">
            <h2>Check your email</h2>
            <p>We sent a sign-in link to <strong>{email}</strong>. It works once and expires in 15 minutes.</p>
            <p className="quiet">No email after a few minutes? Check junk, then <button className="link" onClick={() => setState("idle")}>send another</button>.</p>
          </div>
        ) : (
          <form onSubmit={submit}>
            <h2>Sign in</h2>
            <p className="quiet">Use your work email. We'll send you a link, so there's no password to remember.</p>
            <label>
              Work email
              <input type="email" required autoComplete="email" value={email} onChange={(e) => setEmail(e.target.value)} autoFocus />
            </label>
            {state === "error" && <p className="error" role="alert">{msg}</p>}
            <button className="primary" disabled={state === "sending"} type="submit">
              {state === "sending" ? "Sending link…" : "Email me a sign-in link"}
            </button>
          </form>
        )}
      </section>
    </div>
  );
}

// The characteristic image: a tidy process line with a hand-written note stuck on it.
function FlowSketch() {
  return (
    <svg className="sketch" viewBox="0 0 520 190" role="img" aria-label="A simple process drawing with a sticky note that says: we actually use a spreadsheet for this">
      <circle cx="30" cy="95" r="16" fill="none" stroke="currentColor" strokeWidth="2" />
      <path d="M46 95h44" stroke="currentColor" strokeWidth="2" markerEnd="url(#a)" />
      <rect x="92" y="70" width="112" height="50" rx="9" fill="none" stroke="currentColor" strokeWidth="2" />
      <text x="148" y="100" textAnchor="middle" fontSize="13" fill="currentColor">Check rent paid</text>
      <path d="M204 95h40" stroke="currentColor" strokeWidth="2" markerEnd="url(#a)" />
      <path d="M270 69l26 26-26 26-26-26z" fill="none" stroke="currentColor" strokeWidth="2" />
      <path d="M262 87l16 16M278 87l-16 16" stroke="currentColor" strokeWidth="2" />
      <path d="M296 95h44" stroke="currentColor" strokeWidth="2" markerEnd="url(#a)" />
      <rect x="342" y="70" width="112" height="50" rx="9" fill="none" stroke="currentColor" strokeWidth="2" />
      <text x="398" y="100" textAnchor="middle" fontSize="13" fill="currentColor">Send reminder</text>
      <path d="M454 95h30" stroke="currentColor" strokeWidth="2" markerEnd="url(#a)" />
      <circle cx="500" cy="95" r="14" fill="none" stroke="currentColor" strokeWidth="5" />
      <g transform="rotate(-4 205 150)">
        <rect x="150" y="128" width="166" height="58" fill="var(--marker)" />
        <text x="160" y="152" fontSize="14" fill="var(--ink)" fontStyle="italic">we actually use a</text>
        <text x="160" y="172" fontSize="14" fill="var(--ink)" fontStyle="italic">spreadsheet for this</text>
      </g>
      <defs>
        <marker id="a" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto">
          <path d="M0 0L10 5L0 10z" fill="currentColor" />
        </marker>
      </defs>
    </svg>
  );
}
