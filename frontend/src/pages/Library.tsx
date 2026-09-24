import { useEffect, useState } from "react";
import { api, type Artifact, type ProcessRow } from "../lib/api";
import { KINDS, LAYERS, STATUS, label, size } from "../lib/labels";
import { useSession } from "../lib/session";

export default function Library() {
  const [rows, setRows] = useState<Artifact[] | null>(null);
  const [processes, setProcesses] = useState<ProcessRow[]>([]);
  const [pid, setPid] = useState("");
  const [open, setOpen] = useState<Artifact | null>(null);
  const [reason, setReason] = useState("");
  const [error, setError] = useState("");
  const { me } = useSession();
  useEffect(() => { api.get<ProcessRow[]>("/api/processes").then(setProcesses); }, []);
  useEffect(() => { api.get<Artifact[]>(`/api/artifacts${pid ? `?process_id=${pid}` : ""}`).then(setRows); }, [pid]);

  const withdraw = async (a: Artifact) => {
    if (!confirm(`Withdraw "${a.title}"? It will no longer be used in the review.`)) return;
    await api.send("POST", `/api/artifacts/${a.id}/withdraw`);
    setOpen(null);
    setRows((r) => r?.filter((x) => x.id !== a.id) ?? null);
  };
  // Admins can delete a file straight away, for example an ID document shared by mistake.
  const purge = async (a: Artifact) => {
    setError("");
    try {
      await api.send("POST", `/api/admin/artifacts/${a.id}/purge`, { reason });
      setOpen(null);
      setReason("");
      setRows((r) => r?.filter((x) => x.id !== a.id) ?? null);
    } catch (e) { setError((e as Error).message); }
  };

  return (
    <div className="library">
      <div className="bar">
        <h1>Files</h1>
        <label className="inline">Process
          <select value={pid} onChange={(e) => setPid(e.target.value)}>
            <option value="">All</option>
            {processes.map((p) => <option key={p.id} value={p.id}>{p.name} ({p.artifact_count})</option>)}
          </select>
        </label>
      </div>
      {rows === null ? <p className="quiet">Loading…</p> : rows.length === 0 ? <p className="quiet">No files here yet.</p> : (
        <div className="tablewrap">
          <table>
            <thead><tr><th>File</th><th>Shows</th><th>Process</th><th>Shared by</th><th>Status</th></tr></thead>
            <tbody>
              {rows.map((a) => (
                <tr key={a.id} onClick={() => setOpen(a)} tabIndex={0} onKeyDown={(e) => e.key === "Enter" && setOpen(a)}>
                  <td><strong>{a.title}</strong><div className="quiet">{a.original_filename} · {size(a.size_bytes)}</div></td>
                  <td>{label(LAYERS, a.layer)}{a.personal_info === "yes" && <span className="pi">Personal info</span>}</td>
                  <td>{a.processes.map((p) => p.name).join(", ")}</td>
                  <td>{a.uploaded_by}</td>
                  <td><span className={`status s-${a.status}`}>{STATUS[a.status] ?? a.status}</span></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      {open && (
        <aside className="drawer" aria-label="File detail">
          <button className="link close" onClick={() => { setOpen(null); setError(""); }}>Close</button>
          <h2>{open.title}</h2>
          <p>{open.description || <span className="quiet">No description given.</span>}</p>
          <dl>
            <dt>Kind</dt><dd>{label(KINDS, open.kind)}</dd>
            <dt>Shows</dt><dd>{label(LAYERS, open.layer)}</dd>
            <dt>Used</dt><dd>{open.frequency || "Not said"}</dd>
            <dt>Comes from</dt><dd>{open.source_system || "Not said"}</dd>
            <dt>Kept by</dt><dd>{open.maintained_by || "Not said"}</dd>
          </dl>
          {open.profile && (
            <section className="profile">
              <h3>First read</h3>
              <p>{open.profile.summary}</p>
              {open.profile.sheets && (
                <ul>{open.profile.sheets.map((s) => <li key={s.name}>{s.name}{s.state !== "visible" ? ` (${s.state})` : ""}: {s.dimensions}, {s.formulas} formulas</li>)}</ul>
              )}
              {open.profile.preview && <pre>{open.profile.preview.slice(0, 600)}</pre>}
            </section>
          )}
          <div className="actions">
            {open.status === "quarantined"
              ? <p className="error">The malware check flagged this file, so it can't be downloaded.</p>
              : <a className="button" href={`/api/artifacts/${open.id}/file`}>Download</a>}
            {(open.uploaded_by === me?.email || me?.role === "admin") && <button onClick={() => withdraw(open)}>Withdraw</button>}
          </div>
          {me?.role === "admin" && (
            <section>
              <h3>Delete now</h3>
              <p className="quiet">Removes the file from the server straight away. The record that it was shared stays in the audit log.</p>
              <label>Why<input value={reason} onChange={(e) => setReason(e.target.value)} placeholder="For example: holds a tenant's licence" /></label>
              {error && <p className="error" role="alert">{error}</p>}
              <button onClick={() => purge(open)} disabled={reason.trim().length < 3}>Delete the file</button>
            </section>
          )}
        </aside>
      )}
    </div>
  );
}
