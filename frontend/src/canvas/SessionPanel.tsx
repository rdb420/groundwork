// Record a mapping conversation. Audio goes up in 30-second files so transcription can run
// while the session continues. Each file is a fresh recorder, so every chunk decodes alone.
// Stop waits until the last part has uploaded before it ends the recording, and failed uploads
// retry, because the server refuses parts that arrive long after the end.
import { useEffect, useRef, useState } from "react";
import { api } from "../lib/api";

type Seg = { recording_id: string; seq: number; status: string; text: string };
const CHUNK_MS = 30_000;
const RETRIES = [2_000, 5_000, 15_000];
const wait = (ms: number) => new Promise((r) => setTimeout(r, ms));

export default function SessionPanel({ boardId, transcriptionOn, onRecordingChange }: { boardId: string; transcriptionOn: boolean; onRecordingChange: (on: boolean) => void }) {
  const [consent, setConsent] = useState("");
  const [agreed, setAgreed] = useState(false);
  const [rec, setRec] = useState<{ id: string } | null>(null);
  const [segs, setSegs] = useState<Seg[]>([]);
  const [error, setError] = useState("");
  const [seconds, setSeconds] = useState(0);
  const [stopping, setStopping] = useState(false);
  const stream = useRef<MediaStream | null>(null);
  const running = useRef(false);
  const seq = useRef(0);
  const uploads = useRef<Promise<void>[]>([]);
  const stopCurrent = useRef<() => Promise<void>>(async () => {});

  const load = () => api.get<Seg[]>(`/api/boards/${boardId}/transcript`).then(setSegs).catch(() => {});
  useEffect(() => { load(); const t = setInterval(load, 5000); return () => clearInterval(t); }, [boardId]);
  useEffect(() => {
    if (!rec) return;
    const t = setInterval(() => setSeconds((s) => s + 1), 1000);
    return () => clearInterval(t);
  }, [rec]);

  // Send one part, retrying a few times. The server ignores a part it already has.
  const send = async (rid: string, n: number, blob: Blob, name: string) => {
    for (let attempt = 0; ; attempt++) {
      const form = new FormData();
      form.append("file", blob, name);
      try {
        await api.upload(`/api/recordings/${rid}/chunks?seq=${n}`, form);
        return;
      } catch (e) {
        const status = (e as { status?: number }).status ?? 0;
        if (attempt >= RETRIES.length || (status >= 400 && status < 500 && status !== 429)) {
          setError(`Part ${n + 1} of the recording didn't upload: ${(e as Error).message}`);
          return;
        }
        await wait(RETRIES[attempt]);
      }
    }
  };

  const segment = (rid: string) => {
    if (!stream.current) return;
    const mime = MediaRecorder.isTypeSupported("audio/webm;codecs=opus") ? "audio/webm;codecs=opus" : "audio/mp4";
    const r = new MediaRecorder(stream.current, { mimeType: mime });
    const parts: Blob[] = [];
    let stopped: () => void = () => {};
    const done = new Promise<void>((res) => { stopped = res; });
    r.ondataavailable = (e) => { if (e.data.size) parts.push(e.data); };
    r.onstop = () => {
      const n = seq.current++;
      uploads.current.push(send(rid, n, new Blob(parts, { type: mime }), `chunk.${mime.includes("webm") ? "webm" : "m4a"}`));
      stopped();
      if (running.current) segment(rid);
    };
    r.start();
    setTimeout(() => r.state !== "inactive" && r.stop(), CHUNK_MS);
    stopCurrent.current = () => { if (r.state !== "inactive") r.stop(); return done; };
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
    uploads.current = [];
    running.current = true;
    setSeconds(0);
    setRec(r);
    onRecordingChange(true);
    segment(r.id);
  };

  // Stop recording, wait for every part to upload, then end the recording on the server.
  const finish = async (rid: string) => {
    running.current = false;
    await stopCurrent.current();
    stream.current?.getTracks().forEach((t) => t.stop());
    await Promise.allSettled(uploads.current);
    await api.send("POST", `/api/recordings/${rid}/end`);
  };

  const stop = async () => {
    if (!rec) return;
    setStopping(true);
    try {
      await finish(rec.id);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setStopping(false);
      setRec(null);
      onRecordingChange(false);
      setTimeout(load, 1500);
    }
  };

  // Leaving the map mid-recording still saves the last part and ends the recording.
  const recRef = useRef(rec);
  recRef.current = rec;
  useEffect(() => () => { if (recRef.current && running.current) void finish(recRef.current.id).catch(() => {}); }, []);
  useEffect(() => {
    if (!rec) return;
    const warn = (e: BeforeUnloadEvent) => { e.preventDefault(); };
    window.addEventListener("beforeunload", warn);
    return () => window.removeEventListener("beforeunload", warn);
  }, [rec]);

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
          <span className="dot" aria-hidden="true" /> {stopping ? "Saving the last part…" : `Recording ${mm}`}
          <button onClick={stop} disabled={stopping}>Stop</button>
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
