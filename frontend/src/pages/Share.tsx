import { useEffect, useState } from "react";
import { api, type ProcessRow } from "../lib/api";
import { FREQ, KINDS, LAYERS, size } from "../lib/labels";
import ProcessPicker from "../components/ProcessPicker";
import { Button, Check, DropZone, Field, FileCard, OptionGroup, Segmented } from "../ui";

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
  const [error, setError] = useState("");

  useEffect(() => { api.get<ProcessRow[]>("/api/processes").then(setProcesses); }, []);

  const add = (picked: File[]) => {
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
    <form className="gw-share" onSubmit={send}>
      <h1>Share files</h1>
      <p className="lede">Anything you use to get the work done counts. Rough is fine. Unofficial is especially welcome.</p>

      <DropZone onFiles={add} />

      {files.length > 0 && (
        <>
          <section className="gw-step">
            <h2>Each file</h2>
            {files.map((f, i) => (
              <FileCard key={i} name={f.file.name} size={size(f.file.size)} state={f.state} note={f.note}
                onRemove={() => setFiles((x) => x.filter((_, j) => j !== i))}>
                <Field label="What is it?" required value={f.title} disabled={f.state === "done"} onChange={(e) => patch(i, { title: e.target.value })} />
                <Field label="Kind of file" as="select" options={KINDS} value={f.kind} disabled={f.state === "done"} onChange={(e) => patch(i, { kind: e.target.value })} />
                <Field label="What do you use it for?" hint="Optional" as="textarea" value={f.description} disabled={f.state === "done"}
                  onChange={(e) => patch(i, { description: e.target.value })}
                  placeholder="For example: I update this every Monday from the bank statement, then email it to Dean." />
              </FileCard>
            ))}
          </section>

          <section className="gw-step">
            <h2>Which part of the work do these belong to?</h2>
            <ProcessPicker processes={processes} selected={pids} newNames={newNames} onChange={(s, n) => { setPids(s); setNewNames(n); }} />
            <Field label="Where in that work are they used?" hint="Optional" value={stepNote} onChange={(e) => setStepNote(e.target.value)}
              placeholder="For example: after the tenant signs, before keys are handed over" />
          </section>

          <section className="gw-step">
            <h2 id="layer-q">What do they show?</h2>
            <OptionGroup name="layer" ariaLabelledBy="layer-q" options={LAYERS.map(([value, label, hint]) => ({ value, label, hint }))}
              value={layer} onChange={setLayer} />
          </section>

          <section className="gw-step">
            <h2 id="pi-q">Do they contain personal information about tenants, borrowers or staff?</h2>
            <p className="quiet">Names, contact details, bank details, ID, rent or loan history. We store these files on the office server and keep them out of cloud AI. If you're not sure, we treat them as personal.</p>
            <Segmented name="pi" ariaLabel="Personal information" value={personal} onChange={setPersonal}
              options={[["yes", "Yes"], ["no", "No"], ["unsure", "Not sure"]]} />
          </section>

          <details className="gw-step">
            <summary>Add more detail <span className="quiet">Optional, and very helpful</span></summary>
            <Field label="How often is it used?" as="select" options={FREQ} value={frequency} onChange={(e) => setFrequency(e.target.value)} />
            <Field label="Which system does the information come from?" value={sourceSystem} onChange={(e) => setSourceSystem(e.target.value)}
              placeholder="For example: Xero, bank portal, property software, typed in by hand" />
            <Field label="Who keeps it up to date?" value={maintainedBy} onChange={(e) => setMaintainedBy(e.target.value)} />
            <Check checked={isCurrent} onChange={(e) => setIsCurrent(e.target.checked)}> This is the version in use today</Check>
            <Field label="What would break if this disappeared tomorrow?" as="textarea" value={ifGone} onChange={(e) => setIfGone(e.target.value)} />
          </details>

          {error && <p className="error" role="alert">{error}</p>}
          <div className="gw-actions">
            {allDone ? (
              <Button variant="primary" onClick={() => setFiles([])}>Share more files</Button>
            ) : (
              <Button variant="primary" type="submit" disabled={files.some((f) => f.state === "sending")}>
                Share {files.filter((f) => f.state !== "done").length} file{files.length === 1 ? "" : "s"}
              </Button>
            )}
          </div>
        </>
      )}
    </form>
  );
}
