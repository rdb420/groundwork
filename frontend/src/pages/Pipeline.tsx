import { useEffect, useState } from "react";
import { api } from "../lib/api";
import { Button, Rows, Status, Tiles } from "../ui";

type Status = {
  enabled: boolean;
  services: Record<string, string | boolean>;
  files: Record<string, number>;
  documents: Record<string, number>;
  waiting: Record<string, number>;
  failed_jobs: Record<string, number>;
  attention: { document_id: string; source_type: string; source_id: string; title: string; status: string; stage: string; note: string; converter: string }[];
};
const SERVICE: Record<string, string> = { storage: "File storage", mineru: "MinerU conversion", gotenberg: "Office conversion", transcription: "Transcription", embeddings: "Embeddings", qdrant: "Vector index", extraction: "Entity extraction", graph: "Knowledge graph", ontology: "Ontology version" };
const STAGE: [string, string][] = [["convert", "Convert again"], ["index", "Index again"], ["extract", "Extract again"], ["graph", "Rebuild the graph"]];

// Where every file is in the ingestion pipeline, what needs attention, and reprocessing.
export default function Pipeline() {
  const [s, setS] = useState<Status | null>(null);
  const [msg, setMsg] = useState("");
  const [error, setError] = useState("");
  const load = () => api.get<Status>("/api/admin/pipeline").then(setS).catch((e) => setError(e.message));
  useEffect(() => { load(); const t = setInterval(load, 10_000); return () => clearInterval(t); }, []);
  const act = async (fn: () => Promise<{ queued?: number }>, done: (r: { queued?: number }) => string) => {
    setError(""); setMsg("");
    try { setMsg(done(await fn())); load(); } catch (e) { setError((e as Error).message); }
  };
  if (!s) return error ? <p className="error">{error}</p> : <p className="quiet">Loading…</p>;
  return (
    <div>
      <h1>Pipeline</h1>
      <p className="lede">{s.enabled ? "Every clean file is converted to Markdown, indexed for search, and its entities go into the knowledge graph." : "The pipeline is switched off (GW_PIPELINE_ENABLED)."}</p>
      <Tiles items={Object.entries(s.services).map(([k, v]) => ({ label: SERVICE[k] ?? k, value: v === true ? "Set up" : v === false ? "Not set up" : String(v), small: true }))} />
      <h2>Files</h2>
      <Rows items={Object.entries(s.files).map(([k, v]) => [k, `${v} file${v === 1 ? "" : "s"}`, null])} />
      {Object.keys(s.waiting).length > 0 && <p className="quiet">Waiting: {Object.entries(s.waiting).map(([k, v]) => `${k} ${v}`).join(", ")}</p>}
      {Object.keys(s.failed_jobs).length > 0 && <p className="error">Failed for good: {Object.entries(s.failed_jobs).map(([k, v]) => `${k} ${v}`).join(", ")}</p>}
      <h2>Needs attention</h2>
      {s.attention.length === 0 ? <p className="quiet">Nothing.</p> : (
        <Rows>
          {s.attention.map((a) => (
            <li key={a.document_id}>
              <span><strong>{a.title || a.source_id}</strong><div className="quiet">{a.note || a.converter}</div></span>
              <Status tone={a.status === "failed" ? "error" : "info"}>{a.status === "partial" ? "Partly done" : a.status === "skipped" ? "Skipped" : "Failed"}</Status>
              {a.source_type === "artifact" && (
                <Button onClick={() => act(() => api.send("POST", `/api/admin/artifacts/${a.source_id}/reprocess`, { stage: a.status === "partial" ? "extract" : "convert" }), () => "Queued.")}>Try again</Button>
              )}
            </li>
          ))}
        </Rows>
      )}
      <h2>Reprocess everything</h2>
      <p className="quiet">After pinning a new ontology version, extract again. After changing the chunk size or the embedding models, index again.</p>
      <div className="gw-actions">
        {STAGE.map(([k, l]) => <Button key={k} onClick={() => act(() => api.send("POST", "/api/admin/pipeline/reprocess", { stage: k }), (r) => `Queued ${r.queued} document${r.queued === 1 ? "" : "s"}.`)}>{l}</Button>)}
        <Button onClick={() => act(() => api.send("POST", "/api/admin/pipeline/backfill"), (r) => `Queued ${r.queued} older file${r.queued === 1 ? "" : "s"}.`)}>Queue files shared before the pipeline</Button>
      </div>
      {msg && <p role="status">{msg}</p>}
      {error && <p className="error" role="alert">{error}</p>}
    </div>
  );
}
