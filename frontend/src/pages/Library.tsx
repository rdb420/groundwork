import { useEffect, useState } from "react";
import { api, type Artifact, type ProcessRow } from "../lib/api";
import { KINDS, LAYERS, PIPELINE, STATUS, label, size } from "../lib/labels";
import { useSession } from "../lib/session";
import { Button, DataTable, DetailList, Drawer, Field, LinkButton, Status, Tag, artifactTone } from "../ui";

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
    <div>
      <div className="gw-bar">
        <h1>Files</h1>
        <Field label="Process" as="select" className="gw-inline" value={pid} onChange={(e) => setPid(e.target.value)}>
          <option value="">All</option>
          {processes.map((p) => <option key={p.id} value={p.id}>{p.name} ({p.artifact_count})</option>)}
        </Field>
      </div>
      {rows === null ? <p className="quiet">Loading…</p> : rows.length === 0 ? <p className="quiet">No files here yet.</p> : (
        <DataTable rows={rows} onRowClick={setOpen} columns={[
          { key: "title", label: "File", render: (a) => <><strong>{a.title}</strong><div className="quiet">{a.original_filename} · {size(a.size_bytes)}</div></> },
          { key: "layer", label: "Shows", render: (a) => <>{label(LAYERS, a.layer)}{a.personal_info === "yes" && <Tag kind="pi" />}</> },
          { key: "processes", label: "Process", render: (a) => a.processes.map((p) => p.name).join(", ") },
          { key: "uploaded_by", label: "Shared by" },
          { key: "status", label: "Status", render: (a) => <>
            <Status tone={artifactTone(a.status)}>{STATUS[a.status] ?? a.status}</Status>
            {a.pipeline_status && PIPELINE[a.pipeline_status] && <div className="quiet small">{PIPELINE[a.pipeline_status]}</div>}
          </> },
        ]} />
      )}
      {open && (
        <Drawer label="File detail" title={open.title} onClose={() => { setOpen(null); setError(""); }}>
          <p>{open.description || <span className="quiet">No description given.</span>}</p>
          <DetailList items={[
            ["Kind", label(KINDS, open.kind)],
            ["Shows", label(LAYERS, open.layer)],
            ["Used", open.frequency || "Not said"],
            ["Comes from", open.source_system || "Not said"],
            ["Kept by", open.maintained_by || "Not said"],
          ]} />
          {open.profile && (
            <section className="gw-profile">
              <h3>First read</h3>
              <p>{open.profile.summary}</p>
              {open.profile.sheets && (
                <ul>{open.profile.sheets.map((s) => <li key={s.name}>{s.name}{s.state !== "visible" ? ` (${s.state})` : ""}: {s.dimensions}, {s.formulas} formulas</li>)}</ul>
              )}
              {open.profile.preview && <pre>{open.profile.preview.slice(0, 600)}</pre>}
            </section>
          )}
          <div className="gw-actions">
            {open.status === "quarantined"
              ? <p className="error">The malware check flagged this file, so it can't be downloaded.</p>
              : <LinkButton href={`/api/artifacts/${open.id}/file`}>Download</LinkButton>}
            {(open.uploaded_by === me?.email || me?.role === "admin") && <Button onClick={() => withdraw(open)}>Withdraw</Button>}
          </div>
          {me?.role === "admin" && (
            <section>
              <h3>Delete now</h3>
              <p className="quiet">Removes the file from the server straight away. The record that it was shared stays in the audit log.</p>
              <Field label="Why" value={reason} onChange={(e) => setReason(e.target.value)} placeholder="For example: holds a tenant's licence" />
              {error && <p className="error" role="alert">{error}</p>}
              <Button onClick={() => purge(open)} disabled={reason.trim().length < 3}>Delete the file</Button>
            </section>
          )}
        </Drawer>
      )}
    </div>
  );
}
