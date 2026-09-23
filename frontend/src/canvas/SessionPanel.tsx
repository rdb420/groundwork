// Record a mapping conversation. Audio goes up in 30-second files so transcription can run
// while the session continues. Each file is a fresh recorder, so every chunk decodes alone.
import { useEffect, useRef, useState } from "react";
import { api } from "../lib/api";

type Seg = { recording_id: string; seq: number; status: string; text: string };
const CHUNK_MS = 30_000;

export default function SessionPanel({ boardId, transcriptionOn, onRecordingChange }: { boardId: string; transcriptionOn: boolean; onRecordingChange: (on: boolean) => void }) {
  const [consent, setConsent] = useState("");
  const [agreed, setAgreed] = useState(false);
  const [rec, setRec] = useState<{ id: string } | null>(null);
  const [segs, setSegs] = useState<Seg[]>([]);
  const [error, setError] = useState("");
  const [seconds, setSeconds] = useState(0);
  const stream = useRef<MediaStream | null>(null);
  const running = useRef(false);
  const seq = useRef(0);
  const stopCurrent = useRef<() => void>(() => {});

  const load = () => api.get<Seg[]>(`/api/boards/${boardId}/transcript`).then(setSegs).catch(() => {});
  useEffect(() => { load(); const t = setInterval(load, 5000); return () => clearInterval(t); }, [boardId]);
  useEffect(() => {
    if (!rec) return;
    const t = setInterval(() => setSeconds((s) => s + 1), 1000);
    return () => clearInterval(t);
  }, [rec]);

  const segment = (rid: string) => {
    if (!stream.current) return;
    const mime = MediaRecorder.isTypeSupported("audio/webm;codecs=opus") ? "audio/webm;codecs=opus" : "audio/mp4";
    const r = new MediaRecorder(stream.current, { mimeType: mime });
    const parts: Blob[] = [];
    r.ondataavailable = (e) => e.data.size && parts.push(e.data);
    r.onstop = async () => {
      const n = seq.current++;
      const form = new FormData();
      form.append("file", new Blob(parts, { type: mime }), `chunk.${mime.includes("webm") ? "webm" : "m4a"}`);
      api.upload(`/api/recordings/${rid}/chunks?seq=${n}`, form).catch((e) => setError((e as Error).message));
      if (running.current) segment(rid);
    };
    r.start();
    setTimeout(() => r.state !== "inactive" && r.stop(), CHUNK_MS);
    stopCurrent.current = () => r.state !== "inactive" && r.stop();
  };

  const start = async () => {
    setError("");
    try {
      stream.current = await navigator.mediaDevices.getUserMedia({ audio: true });
    } catch {
      return setError("The browser didn't allow the microphone. Check the site permissions and try again.");
    }
    const r = await api.send<{ id: string }>("POST", `/api/boards/${boardId}/recordings`, { consent_note: consent });
    seq.current = 0;
    running.current = true;
    setSeconds(0);
    setRec(r);
    onRecordingChange(true);
    segment(r.id);
  };

  const stop = async () => {
    running.current = false;
    stopCurrent.current();
    stream.current?.getTracks().forEach((t) => t.stop());
    if (rec) await api.send("POST", `/api/recordings/${rec.id}/end`);
    setRec(null);
    onRecordingChange(false);
    setTimeout(load, 1500);
  };

  useEffect(() => () => { running.current = false; stream.current?.getTracks().forEach((t) => t.stop()); }, []);

  const mm = `${Math.floor(seconds / 60)}:${String(seconds % 60).padStart(2, "0")}`;
  return (
    <div className="panel-body">
      {!rec ? (
        <div className="consent">
          <label>Who is in the session and agreed to be recorded?
            <input value={consent} onChange={(e) => setConsent(e.target.value)} placeholder="For example: Sam (property manager), Ryan" />
          </label>
          <label className="check"><input type="checkbox" checked={agreed} onChange={(e) => setAgreed(e.target.checked)} /> Everyone present has agreed to this recording</label>
          <button className="primary" disabled={!agreed || consent.trim().length < 3} onClick={start}>Start recording</button>
          {!transcriptionOn && <p className="quiet">Transcription is switched off on the server. Audio is still saved for later.</p>}
        </div>
      ) : (
        <div className="recording" role="status">
          <span className="dot" aria-hidden="true" /> Recording {mm}
          <button onClick={stop}>Stop</button>
        </div>
      )}
      {error && <p className="error" role="alert">{error}</p>}
      <h3>Transcript</h3>
      {segs.length === 0 ? <p className="quiet">Nothing recorded on this map yet.</p> : (
        <div className="transcript">
          {segs.map((s) => (
            <p key={`${s.recording_id}-${s.seq}`} className={`seg s-${s.status}`}>
              {s.status === "done" ? s.text || <em className="quiet">(silence)</em> : s.status === "queued" ? <em className="quiet">Transcribing…</em> : s.status === "skipped" ? <em className="quiet">Audio saved, not transcribed.</em> : <em className="error">Couldn't transcribe this part.</em>}
            </p>
          ))}
        </div>
      )}
    </div>
  );
}
