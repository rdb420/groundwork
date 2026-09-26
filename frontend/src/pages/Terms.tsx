import { useEffect, useState } from "react";
import { api } from "../lib/api";
import { Button, Card, Field, Input, Select, Status, Tag } from "../ui";

type Evidence = { chunk_id: string; text: string; title: string; source_type: string; page: number | null; start_s: number | null; personal_info: boolean };
type Candidate = {
  id: string; kind: "class" | "relation" | "concept"; label: string; occurrences: number; status: string;
  domain: { iri: string; label: string } | null; range: { iri: string; label: string } | null;
  note: string; evidence: Evidence[];
};
type Term = { iri: string; kind: string; label: string };
const KIND: Record<string, string> = { class: "Kind of thing", relation: "Relationship", concept: "Category value" };

// Terms the files and sessions use that the property ontology doesn't have yet. Accept the ones
// worth adding, merge the ones the ontology already covers under another name, reject the rest.
// Accepted terms are exported as a change for the ontology's build script; nothing here edits it.
export default function Terms() {
  const [status, setStatus] = useState("open");
  const [rows, setRows] = useState<Candidate[] | null>(null);
  const [error, setError] = useState("");
  const [exported, setExported] = useState<{ markdown: string; yaml: string } | null>(null);
  const load = () => api.get<Candidate[]>(`/api/ontology/candidates?status=${status}`).then(setRows).catch((e) => setError(e.message));
  useEffect(() => { setRows(null); load(); }, [status]);

  const doExport = async () => {
    setError("");
    try { setExported(await api.send("POST", "/api/ontology/candidates-export")); load(); } catch (e) { setError((e as Error).message); }
  };
  const download = (name: string, text: string) => {
    const a = document.createElement("a");
    a.href = URL.createObjectURL(new Blob([text], { type: "text/plain" }));
    a.download = name;
    a.click();
  };

  return (
    <div>
      <div className="gw-bar">
        <h1>Terms to review</h1>
        <Field label="Show" as="select" className="gw-inline" value={status} onChange={(e) => setStatus(e.target.value)} options={[
          ["open", "Waiting for a decision"], ["accepted", "Accepted"], ["merged", "Merged"], ["rejected", "Rejected"], ["exported", "Exported"],
        ]} />
      </div>
      <p className="lede">Things the files and sessions keep mentioning that the property ontology has no place for yet. Most often seen first.</p>
      {(status === "accepted" || status === "merged") && rows && rows.length > 0 && (
        <p><Button variant="primary" onClick={doExport}>Export accepted terms for the ontology</Button></p>
      )}
      {exported && (
        <div className="gw-proposal">
          <p><strong>Exported.</strong> Add these to property_ontology's build script, build and test a new version, then vendor it here.</p>
          <div className="gw-actions">
            <Button onClick={() => download("ontology-proposals.md", exported.markdown)}>Download the summary</Button>
            <Button onClick={() => download("ontology-terms.yaml", exported.yaml)}>Download the term entries</Button>
          </div>
        </div>
      )}
      {error && <p className="error" role="alert">{error}</p>}
      {!rows ? <p className="quiet">Loading…</p> : rows.length === 0 ? <p className="quiet">Nothing here.</p> : (
        <ul className="gw-cards">{rows.map((c) => <TermCard key={c.id} c={c} onDone={load} />)}</ul>
      )}
    </div>
  );
}

function TermCard({ c, onDone }: { c: Candidate; onDone: () => void }) {
  const [label, setLabel] = useState(c.label);
  const [note, setNote] = useState(c.note);
  const [q, setQ] = useState("");
  const [matches, setMatches] = useState<Term[]>([]);
  const [target, setTarget] = useState("");
  const [error, setError] = useState("");
  useEffect(() => {
    if (q.trim().length < 2) { setMatches([]); return; }
    const t = setTimeout(() => api.get<Term[]>(`/api/ontology/terms?q=${encodeURIComponent(q)}`).then(setMatches).catch(() => {}), 250);
    return () => clearTimeout(t);
  }, [q]);
  const decide = async (action: string, extra: Record<string, string> = {}) => {
    setError("");
    try { await api.send("POST", `/api/ontology/candidates/${c.id}`, { action, label, note, ...extra }); onDone(); }
    catch (e) { setError((e as Error).message); }
  };
  return (
    <Card as="li" header={<>
      <Status>{KIND[c.kind] ?? c.kind}</Status>
      {c.status === "open" ? <Input className="gw-card-title" value={label} onChange={(e) => setLabel(e.target.value)} aria-label="Name" /> : <strong>{c.label}</strong>}
      <span className="quiet">Seen {c.occurrences} time{c.occurrences === 1 ? "" : "s"}</span>
    </>}>
      {c.domain && c.range && <p className="quiet">From {c.domain.label} to {c.range.label}</p>}
      <ul className="gw-evidence-list">
        {c.evidence.map((e) => (
          <li key={e.chunk_id}>
            <span className="quiet">{e.title}{e.page ? `, page ${e.page}` : ""}{e.start_s != null ? `, at ${Math.round(e.start_s)}s` : ""}</span>
            {e.personal_info && <Tag kind="pi" />}
            <blockquote className="gw-evidence">{e.text}</blockquote>
          </li>
        ))}
      </ul>
      {c.status === "open" && (
        <>
          <Field label="Note for the ontology" hint="Optional" value={note} onChange={(e) => setNote(e.target.value)} />
          <div className="gw-actions">
            <Button variant="primary" onClick={() => decide("accept")}>Accept as a new term</Button>
            <Button variant="link" onClick={() => decide("reject")}>Reject</Button>
          </div>
          <details>
            <summary>Or merge into an existing term</summary>
            <Input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Search the ontology" aria-label="Search the ontology" />
            {matches.length > 0 && (
              <Select value={target} onChange={(e) => setTarget(e.target.value)} aria-label="Existing term">
                <option value="">Choose a term</option>
                {matches.map((t) => <option key={t.iri} value={t.iri}>{t.label} ({KIND[t.kind] ?? t.kind})</option>)}
              </Select>
            )}
            <Button onClick={() => decide("merge", { merged_into_iri: target })} disabled={!target}>Merge</Button>
          </details>
        </>
      )}
      {c.status !== "open" && c.status !== "exported" && <Button variant="link" onClick={() => decide("reopen")}>Reopen</Button>}
      {error && <p className="error" role="alert">{error}</p>}
    </Card>
  );
}
