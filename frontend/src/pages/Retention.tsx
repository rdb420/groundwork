import { useEffect, useState } from "react";
import { api } from "../lib/api";
import { Button, Rows } from "../ui";

type Status = {
  withdrawn_days: number; audio_days: number; auto: boolean; backup_keep_days: number;
  files: { id: string; title: string; withdrawn_at: string | null }[];
  audio: { id: string; board_id: string; ended_at: string }[];
};

const day = (d: string | null) => (d ? new Date(d).toLocaleDateString("en-AU") : "an unknown date");
const period = (n: number, what: string) => (n > 0 ? `${what} after ${n} days` : `${what}: kept`);

// Retention rules from docs/PRIVACY.md, and what they would delete now.
export default function Retention() {
  const [s, setS] = useState<Status | null>(null);
  const [busy, setBusy] = useState(false);
  const [done, setDone] = useState("");
  const [error, setError] = useState("");
  const load = () => api.get<Status>("/api/admin/retention").then(setS).catch((e) => setError(e.message));
  useEffect(() => { load(); }, []);

  const run = async () => {
    setBusy(true); setError(""); setDone("");
    try {
      const r = await api.send<{ files: number; audio: number }>("POST", "/api/admin/retention/run");
      setDone(`Deleted ${r.files} file${r.files === 1 ? "" : "s"} and the audio of ${r.audio} recording${r.audio === 1 ? "" : "s"}.`);
      await load();
    } catch (e) { setError((e as Error).message); } finally { setBusy(false); }
  };

  if (error && !s) return <p className="error">{error}</p>;
  if (!s) return <p className="quiet">Loading…</p>;
  const nothing = s.files.length === 0 && s.audio.length === 0;
  return (
    <div>
      <h1>Retention</h1>
      <ul>
        <li>{period(s.withdrawn_days, "Withdrawn files are deleted")}</li>
        <li>{period(s.audio_days, "Session audio is deleted")}, counted from the end of the recording. Transcripts stay with the map.</li>
        <li>Backups hold deleted files for up to {s.backup_keep_days} more days.</li>
        <li>{s.auto ? "The worker deletes what is due once a day." : "Nothing is deleted until someone runs it here."}</li>
      </ul>
      <p className="quiet">Change the periods in the server settings (GW_RETENTION_*) after agreeing them in the privacy impact assessment.</p>

      <h2>Due now</h2>
      {nothing ? <p className="quiet">Nothing is due.</p> : (
        <Rows>
          {s.files.map((f) => <li key={f.id}><strong>{f.title}</strong><span className="quiet">Withdrawn {day(f.withdrawn_at)}</span><span>File</span></li>)}
          {s.audio.map((a) => <li key={a.id}><a href={`/maps/${a.board_id}`}>Session recording</a><span className="quiet">Ended {day(a.ended_at)}</span><span>Audio</span></li>)}
        </Rows>
      )}
      {error && <p className="error" role="alert">{error}</p>}
      {done && <p role="status">{done}</p>}
      <Button variant="primary" onClick={run} disabled={busy || nothing}>{busy ? "Deleting…" : "Delete what is due"}</Button>
    </div>
  );
}
