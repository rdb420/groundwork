import { useEffect, useMemo, useState } from "react";
import { api, type ProcessRow } from "../lib/api";

const STATUS_LABEL: Record<string, string> = { proposed: "Proposed", confirmed: "Confirmed", retired: "Retired" };

// The process catalogue. Staff propose names as they share files; analysts confirm, rename,
// group, merge duplicates and retire what turns out not to be a process.
export default function ProcessList() {
  const [rows, setRows] = useState<ProcessRow[] | null>(null);
  const [showRetired, setShowRetired] = useState(false);
  const [open, setOpen] = useState<ProcessRow | null>(null);
  const load = () => api.get<ProcessRow[]>("/api/processes?include_retired=true").then(setRows);
  useEffect(() => { load(); }, []);

  const visible = useMemo(() => (rows ?? []).filter((p) => showRetired || p.status !== "retired"), [rows, showRetired]);
  const groups = useMemo(() => {
    const tops = visible.filter((p) => !p.parent_id || !visible.some((q) => q.id === p.parent_id));
    return tops.map((t) => ({ top: t, kids: visible.filter((p) => p.parent_id === t.id) }));
  }, [visible]);

  if (!rows) return <p className="quiet">Loading…</p>;
  const item = (p: ProcessRow, child: boolean) => (
    <li key={p.id} className={child ? "indent" : ""}>
      <button className="link" onClick={() => setOpen(p)}>{p.name}</button>
      <span className="quiet">{p.artifact_count} file{p.artifact_count === 1 ? "" : "s"} · {p.board_count} map{p.board_count === 1 ? "" : "s"}{p.owner_email ? ` · ${p.owner_email}` : ""}</span>
      <span className={`status ${p.status === "confirmed" ? "s-processed" : p.status === "retired" ? "s-failed" : ""}`}>{STATUS_LABEL[p.status] ?? p.status}</span>
    </li>
  );

  return (
    <div className="processes">
      <div className="bar">
        <h1>Process list</h1>
        <label className="check"><input type="checkbox" checked={showRetired} onChange={(e) => setShowRetired(e.target.checked)} /> Show retired</label>
      </div>
      <p className="lede">Staff add names in their own words. Confirm the ones that are real processes, merge duplicates, and give each an owner to check its map.</p>
      <ul className="rows">{groups.flatMap(({ top, kids }) => [item(top, false), ...kids.map((k) => item(k, true))])}</ul>
      {open && <Editor key={open.id} p={open} all={rows} onClose={() => setOpen(null)} onSaved={() => { setOpen(null); load(); }} />}
    </div>
  );
}

function Editor({ p, all, onClose, onSaved }: { p: ProcessRow; all: ProcessRow[]; onClose: () => void; onSaved: () => void }) {
  const [name, setName] = useState(p.name);
  const [description, setDescription] = useState(p.description);
  const [owner, setOwner] = useState(p.owner_email);
  const [status, setStatus] = useState(p.status);
  const [parent, setParent] = useState(p.parent_id ?? "");
  const [into, setInto] = useState("");
  const [error, setError] = useState("");

  // A process can't sit under itself or under one of its own sub-processes.
  const below = useMemo(() => {
    const out = new Set([p.id]);
    let grew = true;
    while (grew) {
      grew = false;
      for (const q of all) if (q.parent_id && out.has(q.parent_id) && !out.has(q.id)) { out.add(q.id); grew = true; }
    }
    return out;
  }, [p, all]);
  const live = all.filter((q) => q.status !== "retired");

  const save = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    try {
      await api.send("PATCH", `/api/processes/${p.id}`, {
        name, description, status,
        ...(owner.trim() ? { owner_email: owner.trim() } : { clear_owner: true }),
        ...(parent ? { parent_id: parent } : { clear_parent: true }),
      });
      onSaved();
    } catch (err) { setError((err as Error).message); }
  };
  const merge = async () => {
    const target = all.find((q) => q.id === into);
    if (!target || !confirm(`Move everything from "${p.name}" into "${target.name}" and retire "${p.name}"?`)) return;
    setError("");
    try {
      await api.send("POST", `/api/processes/${p.id}/merge`, { into });
      onSaved();
    } catch (err) { setError((err as Error).message); }
  };

  return (
    <aside className="drawer" aria-label="Edit process">
      <button className="link close" onClick={onClose}>Close</button>
      <h2>{p.name}</h2>
      <form onSubmit={save} className="stack">
        <label>Name<input required value={name} onChange={(e) => setName(e.target.value)} /></label>
        <label>What it covers<textarea rows={3} value={description} onChange={(e) => setDescription(e.target.value)} /></label>
        <label>Owner's email <span className="quiet">Who checks this process's map</span>
          <input type="email" value={owner} onChange={(e) => setOwner(e.target.value)} placeholder="name@yshproperty.com.au" /></label>
        <label>Sits under
          <select value={parent} onChange={(e) => setParent(e.target.value)}>
            <option value="">Nothing (a top-level area)</option>
            {live.filter((q) => !below.has(q.id)).map((q) => <option key={q.id} value={q.id}>{q.name}</option>)}
          </select>
        </label>
        <label>Status
          <select value={status} onChange={(e) => setStatus(e.target.value)}>
            {Object.entries(STATUS_LABEL).map(([v, l]) => <option key={v} value={v}>{l}</option>)}
          </select>
        </label>
        {error && <p className="error" role="alert">{error}</p>}
        <button className="primary" type="submit">Save</button>
      </form>
      {p.status !== "retired" && (
        <section>
          <h3>Merge a duplicate</h3>
          <p className="quiet">Its files and maps move to the process you choose, its sub-processes move under it, and this one is retired.</p>
          <label>Merge into
            <select value={into} onChange={(e) => setInto(e.target.value)}>
              <option value="">Choose a process</option>
              {live.filter((q) => !below.has(q.id)).map((q) => <option key={q.id} value={q.id}>{q.name}</option>)}
            </select>
          </label>
          <button onClick={merge} disabled={!into}>Merge</button>
        </section>
      )}
    </aside>
  );
}
