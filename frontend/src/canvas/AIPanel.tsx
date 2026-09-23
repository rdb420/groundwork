import { useEffect, useRef, useState } from "react";
import { api, type Draft } from "../lib/api";
import { Markdown } from "../lib/markdown";

const MODES: [Draft["mode"], string, string][] = [
  ["sop", "Draft the SOP", "Writes a procedure from the map, the conversation and the linked files."],
  ["workflow", "Suggest map changes", "Proposes steps the conversation mentions that the map is missing."],
  ["questions", "What should we ask next?", "Lists the gaps to cover in the next conversation."],
];

type Props = { boardId: string; enabled: boolean; recording: boolean; beforeGenerate: () => Promise<void>; onApply: (d: Draft) => void };

// Every output is a draft. People keep, edit or drop it; nothing changes the map on its own.
export default function AIPanel({ boardId, enabled, recording, beforeGenerate, onApply }: Props) {
  const [drafts, setDrafts] = useState<Draft[]>([]);
  const [guidance, setGuidance] = useState("");
  const [busy, setBusy] = useState<string>("");
  const [error, setError] = useState("");
  const [auto, setAuto] = useState(false);
  const busyRef = useRef(false);

  useEffect(() => { api.get<Draft[]>(`/api/boards/${boardId}/drafts`).then(setDrafts); }, [boardId]);

  const run = async (mode: Draft["mode"]) => {
    if (busyRef.current) return;
    busyRef.current = true;
    setBusy(mode);
    setError("");
    try {
      await beforeGenerate();
      const d = await api.send<Draft>("POST", `/api/boards/${boardId}/generate`, { mode, guidance });
      setDrafts((x) => [d, ...x]);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      busyRef.current = false;
      setBusy("");
    }
  };

  // Live mode: refresh the SOP draft every five minutes while a session is being recorded.
  useEffect(() => {
    if (!auto || !recording) return;
    const t = setInterval(() => run("sop"), 5 * 60_000);
    return () => clearInterval(t);
  }, [auto, recording]);

  const decide = async (d: Draft, decision: "accept" | "discard") => {
    await api.send("POST", `/api/drafts/${d.id}/${decision}`);
    setDrafts((x) => x.map((y) => (y.id === d.id ? { ...y, status: decision === "accept" ? "accepted" : "discarded" } : y)));
  };

  const download = (d: Draft) => {
    const a = document.createElement("a");
    a.href = URL.createObjectURL(new Blob([d.markdown], { type: "text/markdown" }));
    a.download = `${d.mode}-${d.created_at.slice(0, 10)}.md`;
    a.click();
  };

  if (!enabled) return <div className="panel-body"><p className="quiet">AI drafting is switched off on the server. The map, files and transcript still save as normal.</p></div>;

  return (
    <div className="panel-body">
      <label>Anything to focus on? <span className="quiet">Optional</span>
        <textarea rows={2} value={guidance} onChange={(e) => setGuidance(e.target.value)} placeholder="For example: concentrate on what happens when a tenant disputes the amount" />
      </label>
      <div className="modes">
        {MODES.map(([m, l, hint]) => (
          <button key={m} onClick={() => run(m)} disabled={!!busy} title={hint}>{busy === m ? "Drafting…" : l}</button>
        ))}
      </div>
      <label className="check"><input type="checkbox" checked={auto} onChange={(e) => setAuto(e.target.checked)} /> Refresh the SOP every 5 minutes while recording</label>
      {error && <p className="error" role="alert">{error}</p>}
      {drafts.map((d) => (
        <article key={d.id} className={`draft d-${d.status}`}>
          <header>
            <strong>{MODES.find((m) => m[0] === d.mode)?.[1]}</strong>
            <span className="quiet">{new Date(d.created_at).toLocaleTimeString("en-AU", { hour: "numeric", minute: "2-digit" })} · map v{d.board_version} · {d.model}</span>
          </header>
          <Markdown source={d.markdown} />
          {d.status === "draft" && (
            <div className="actions">
              {d.proposal?.nodes?.length ? <button className="primary" onClick={() => { onApply(d); decide(d, "accept"); }}>Add {d.proposal.nodes.length} suggestions to the map</button>
                : <button className="primary" onClick={() => decide(d, "accept")}>Keep</button>}
              <button onClick={() => download(d)}>Download</button>
              <button className="link" onClick={() => decide(d, "discard")}>Discard</button>
            </div>
          )}
          {d.status !== "draft" && <p className="quiet">{d.status === "accepted" ? "Kept" : "Discarded"}</p>}
        </article>
      ))}
    </div>
  );
}
