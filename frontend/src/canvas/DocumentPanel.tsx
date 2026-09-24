// The living SOP or work instruction for this map. The session reviewer proposes revisions;
// a person saves them.
import { useEffect, useState } from "react";
import { api, type Draft } from "../lib/api";
import { Markdown } from "../lib/markdown";

type Props = { boardId: string; docKind: "sop" | "wi"; setDocKind: (k: "sop" | "wi") => void; proposal: Draft | null; clearProposal: () => void };

export default function DocumentPanel({ boardId, docKind, setDocKind, proposal, clearProposal }: Props) {
  const [text, setText] = useState("");
  const [saved, setSaved] = useState("");
  const [editing, setEditing] = useState(false);
  const [error, setError] = useState("");
  const [stale, setStale] = useState(false);
  const [version, setVersion] = useState(0);

  const load = () => api.get<{ markdown: string; doc_kind: "sop" | "wi"; version: number }>(`/api/boards/${boardId}/document`).then((d) => {
    setText(d.markdown); setSaved(d.markdown); setVersion(d.version); setStale(false); setError("");
    if (d.markdown) setDocKind(d.doc_kind);
  });
  useEffect(() => { load(); }, [boardId]);

  // Saves carry the version this person started from, so nobody overwrites a colleague's edit.
  const save = async (md: string) => {
    setError("");
    try {
      const r = await api.send<{ version: number }>("PUT", `/api/boards/${boardId}/document`, { markdown: md, doc_kind: docKind, version });
      setText(md); setSaved(md); setVersion(r.version); setEditing(false);
    } catch (e) {
      setStale((e as { status?: number }).status === 409);
      setError((e as Error).message);
    }
  };

  const download = () => {
    const a = document.createElement("a");
    a.href = URL.createObjectURL(new Blob([text], { type: "text/markdown" }));
    a.download = `${docKind === "wi" ? "work-instruction" : "sop"}.md`;
    a.click();
  };

  return (
    <div className="panel-body">
      <div className="segmented small" role="radiogroup" aria-label="Document type">
        <label className={docKind === "sop" ? "on" : ""}><input type="radio" checked={docKind === "sop"} onChange={() => setDocKind("sop")} />Procedure (SOP)</label>
        <label className={docKind === "wi" ? "on" : ""}><input type="radio" checked={docKind === "wi"} onChange={() => setDocKind("wi")} />Work instruction</label>
      </div>
      {proposal && proposal.markdown && proposal.markdown !== saved && (
        <div className="proposal">
          <p><strong>The reviewer revised the document.</strong> {proposal.proposal?.summary}</p>
          <div className="actions">
            <button className="primary" onClick={() => { save(proposal.markdown); clearProposal(); }}>Use the revision</button>
            <button onClick={() => { setText(proposal.markdown); setEditing(true); clearProposal(); }}>Edit it first</button>
            <button className="link" onClick={clearProposal}>Keep mine</button>
          </div>
        </div>
      )}
      {editing ? (
        <>
          <textarea className="doc-edit" value={text} onChange={(e) => setText(e.target.value)} rows={24} aria-label="Document text" />
          <div className="actions"><button className="primary" onClick={() => save(text)}>Save</button><button className="link" onClick={() => { setText(saved); setEditing(false); }}>Cancel</button></div>
        </>
      ) : (
        <>
          {text ? <Markdown source={text} /> : <p className="quiet">No document yet. Run a review from the Live tab, or write one yourself.</p>}
          <div className="actions"><button onClick={() => setEditing(true)}>Edit</button>{text && <button onClick={download}>Download</button>}</div>
        </>
      )}
      {error && <p className="error" role="alert">{error} {stale && <button className="link" onClick={() => { void navigator.clipboard?.writeText(text); load(); setEditing(false); }}>Copy my text and reload</button>}</p>}
    </div>
  );
}
