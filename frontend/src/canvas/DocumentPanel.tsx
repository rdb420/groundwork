// The living SOP or work instruction for this map. The session reviewer proposes revisions;
// a person saves them.
import { useEffect, useState } from "react";
import { api, type Draft } from "../lib/api";
import { Markdown } from "../lib/markdown";
import { Button, Segmented, TextArea } from "../ui";

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
    <div className="gw-panel-body">
      <Segmented name="doc-kind" small ariaLabel="Document type" value={docKind} onChange={setDocKind}
        options={[["sop", "Procedure (SOP)"], ["wi", "Work instruction"]]} />
      {proposal && proposal.markdown && proposal.markdown !== saved && (
        <div className="gw-proposal">
          <p><strong>The reviewer revised the document.</strong> {proposal.proposal?.summary}</p>
          <div className="gw-actions">
            <Button variant="primary" onClick={() => { save(proposal.markdown); clearProposal(); }}>Use the revision</Button>
            <Button onClick={() => { setText(proposal.markdown); setEditing(true); clearProposal(); }}>Edit it first</Button>
            <Button variant="link" onClick={clearProposal}>Keep mine</Button>
          </div>
        </div>
      )}
      {editing ? (
        <>
          <TextArea className="gw-doc-edit" value={text} onChange={(e) => setText(e.target.value)} rows={24} aria-label="Document text" />
          <div className="gw-actions"><Button variant="primary" onClick={() => save(text)}>Save</Button><Button variant="link" onClick={() => { setText(saved); setEditing(false); }}>Cancel</Button></div>
        </>
      ) : (
        <>
          {text ? <Markdown source={text} /> : <p className="quiet">No document yet. Run a review from the Live tab, or write one yourself.</p>}
          <div className="gw-actions"><Button onClick={() => setEditing(true)}>Edit</Button>{text && <Button onClick={download}>Download</Button>}</div>
        </>
      )}
      {error && <p className="error" role="alert">{error} {stale && <Button variant="link" onClick={() => { void navigator.clipboard?.writeText(text); load(); setEditing(false); }}>Copy my text and reload</Button>}</p>}
    </div>
  );
}
