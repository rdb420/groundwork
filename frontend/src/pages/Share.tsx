import { useEffect, useRef, useState } from "react";
import { api, type ProcessRow } from "../lib/api";
import { FREQ, KINDS, LAYERS, size } from "../lib/labels";
import ProcessPicker from "../components/ProcessPicker";

type Pending = { file: File; title: string; description: string; kind: string; state: "ready" | "sending" | "done" | "error"; note?: string };

const guessKind = (name: string) => {
  const ext = name.split(".").pop()?.toLowerCase() || "";
  if (["xlsx", "xlsm", "xls", "csv", "tsv", "ods"].includes(ext)) return "spreadsheet";
  if (["png", "jpg", "jpeg", "gif", "webp", "heic"].includes(ext)) return "photo";
  if (["msg", "eml"].includes(ext)) return "email";
  if (["vsdx", "bpmn"].includes(ext)) return "diagram";
  return "other";
};

// Two layers of questions: a short shared set that applies to the whole batch, and a title
// per file. The optional detail sits behind a disclosure so the first upload stays quick.
export default function Share() {
  const [processes, setProcesses] = useState<ProcessRow[]>([]);
  const [files, setFiles] = useState<Pending[]>([]);
  const [pids, setPids] = useState<string[]>([]);
  const [newNames, setNewNames] = useState<string[]>([]);
  const [stepNote, setStepNote] = useState("");
  const [layer, setLayer] = useState("unsure");
  const [personal, setPersonal] = useState("");
  const [frequency, setFrequency] = useState("");
  const [sourceSystem, setSourceSystem] = useState("");
  const [maintainedBy, setMaintainedBy] = useState("");
  const [ifGone, setIfGone] = useState("");
  const [isCurrent, setIsCurrent] = useState(true);
  const [drag, setDrag] = useState(false);
  const [error, setError] = useState("");
  const input = useRef<HTMLInputElement>(null);

  useEffect(() => { api.get<ProcessRow[]>("/api/processes").then(setProcesses); }, []);

  const add = (list: FileList | null) => {
    if (!list) return;
    const picked = Array.from(list); // copy now: resetting the input empties the live FileList
    setFiles((f) => [...f, ...picked.map((file) => ({
      file, title: file.name.replace(/\.[^.]+$/, "").replace(/[_-]+/g, " "), description: "", kind: guessKind(file.name), state: "ready" as const,
    }))]);
  };
  const patch = (i: number, p: Partial<Pending>) => setFiles((f) => f.map((x, j) => (j === i ? { ...x, ...p } : x)));

  const send = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    if (!personal) return setError("Answer the personal information question so we know how to handle these files.");
    if (!pids.length && !newNames.length) return setError("Pick the work these files belong to, or add it in your own words.");
    for (let i = 0; i < files.length; i++) {
      const f = files[i];
      if (f.state === "done") continue;
      patch(i, { state: "sending" });
      const form = new FormData();
      form.append("file", f.file);
      form.append("meta", JSON.stringify({
        title: f.title, description: f.description, kind: f.kind, layer, frequency, source_system: sourceSystem,
        maintained_by: maintainedBy, personal_info: personal, is_current: isCurrent, if_it_disappeared: ifGone,
        process_ids: pids, new_process_names: newNames, step_note: stepNote,
      }));
      try {
        const r = await api.upload<{ duplicate_of: string | null }>("/api/artifacts", form);
        patch(i, { state: "done", note: r.duplicate_of ? "Someone already shared this exact file. Thanks for confirming it's in use." : undefined });
      } catch (err) {
        patch(i, { state: "error", note: (err as Error).message });
      }
    }
    setNewNames([]);
    api.get<ProcessRow[]>("/api/processes").then(setProcesses);
  };

  const allDone = files.length > 0 && files.every((f) => f.state === "done");

  return (
    <form className="share" onSubmit={send}>
      <h1>Share files</h1>
      <p className="lede">Anything you use to get the work done counts. Rough is fine. Unofficial is especially welcome.</p>

      <div className={`drop ${drag ? "over" : ""}`} onDragOver={(e) => { e.preventDefault(); setDrag(true); }}
        onDragLeave={() => setDrag(false)} onDrop={(e) => { e.preventDefault(); setDrag(false); add(e.dataTransfer.files); }}>
        <p>Drop files here, or</p>
        <button type="button" onClick={() => input.current?.click()}>Choose files</button>
        <input ref={input} type="file" multiple hidden onChange={(e) => { add(e.target.files); e.target.value = ""; }} />
      </div>

      {files.length > 0 && (
        <>
          <section className="step">
            <h2>Each file</h2>
            {files.map((f, i) => (
              <div key={i} className={`filecard f-${f.state}`}>
                <div className="filehead">
                  <span className="fname">{f.file.name}</span>
                  <span className="quiet">{size(f.file.size)}</span>
                  {f.state === "ready" && <button type="button" className="link" onClick={() => setFiles((x) => x.filter((_, j) => j !== i))}>Remove</button>}
                  {f.state === "done" && <span className="status s-processed">Shared</span>}
                  {f.state === "sending" && <span className="status">Sending…</span>}
                </div>
                <label>What is it?<input required value={f.title} disabled={f.state === "done"} onChange={(e) => patch(i, { title: e.target.value })} /></label>
                <label>Kind of file
                  <select value={f.kind} disabled={f.state === "done"} onChange={(e) => patch(i, { kind: e.target.value })}>
                    {KINDS.map(([v, l]) => <option key={v} value={v}>{l}</option>)}
                  </select>
                </label>
                <label>What do you use it for? <span className="quiet">Optional</span>
                  <textarea rows={2} value={f.description} disabled={f.state === "done"} onChange={(e) => patch(i, { description: e.target.value })}
                    placeholder="For example: I update this every Monday from the bank statement, then email it to Dean." />
                </label>
                {f.note && <p className={f.state === "error" ? "error" : "quiet"}>{f.note}</p>}
              </div>
            ))}
          </section>

          <section className="step">
            <h2>Which part of the work do these belong to?</h2>
            <ProcessPicker processes={processes} selected={pids} newNames={newNames} onChange={(s, n) => { setPids(s); setNewNames(n); }} />
            <label>Where in that work are they used? <span className="quiet">Optional</span>
              <input value={stepNote} onChange={(e) => setStepNote(e.target.value)} placeholder="For example: after the tenant signs, before keys are handed over" />
            </label>
          </section>

          <section className="step">
            <h2>What do they show?</h2>
            <div className="options">
              {LAYERS.map(([v, l, hint]) => (
                <label key={v} className={`option ${layer === v ? "on" : ""}`}>
                  <input type="radio" name="layer" value={v} checked={layer === v} onChange={() => setLayer(v)} />
                  <strong>{l}</strong><span>{hint}</span>
                </label>
              ))}
            </div>
          </section>

          <section className="step">
            <h2>Do they contain personal information about tenants, borrowers or staff?</h2>
            <p className="quiet">Names, contact details, bank details, ID, rent or loan history. We store these files on the office server and keep them out of cloud AI.</p>
            <div className="segmented" role="radiogroup">
              {[["yes", "Yes"], ["no", "No"], ["unsure", "Not sure"]].map(([v, l]) => (
                <label key={v} className={personal === v ? "on" : ""}>
                  <input type="radio" name="pi" value={v} checked={personal === v} onChange={() => setPersonal(v)} />{l}
                </label>
              ))}
            </div>
          </section>

          <details className="step">
            <summary>Add more detail <span className="quiet">Optional, and very helpful</span></summary>
            <label>How often is it used?
              <select value={frequency} onChange={(e) => setFrequency(e.target.value)}>{FREQ.map(([v, l]) => <option key={v} value={v}>{l}</option>)}</select>
            </label>
            <label>Which system does the information come from?<input value={sourceSystem} onChange={(e) => setSourceSystem(e.target.value)} placeholder="For example: Xero, bank portal, property software, typed in by hand" /></label>
            <label>Who keeps it up to date?<input value={maintainedBy} onChange={(e) => setMaintainedBy(e.target.value)} /></label>
            <label className="check"><input type="checkbox" checked={isCurrent} onChange={(e) => setIsCurrent(e.target.checked)} /> This is the version in use today</label>
            <label>What would break if this disappeared tomorrow?
              <textarea rows={2} value={ifGone} onChange={(e) => setIfGone(e.target.value)} />
            </label>
          </details>

          {error && <p className="error" role="alert">{error}</p>}
          <div className="actions">
            {allDone ? (
              <button type="button" className="primary" onClick={() => setFiles([])}>Share more files</button>
            ) : (
              <button className="primary" type="submit" disabled={files.some((f) => f.state === "sending")}>
                Share {files.filter((f) => f.state !== "done").length} file{files.length === 1 ? "" : "s"}
              </button>
            )}
          </div>
        </>
      )}
    </form>
  );
}
