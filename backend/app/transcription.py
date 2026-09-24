"""Speech to text. Local first:
- parakeet: rdb420/parakeet-transcription-app (NVIDIA Parakeet TDT) on the inference box, through
  its Gradio HTTP API
- faster_whisper: runs on the host (CPU is fine for small.en)
- openai_compatible: a Whisper server on the inference box
All return the text and, where the provider gives them, timed rows."""
import json
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

import httpx

from . import httpclient, jobs
from .config import get_settings


class TranscriptionError(RuntimeError):
    pass


@dataclass
class Transcript:
    text: str
    rows: list[list] = field(default_factory=list)  # [[start_s, end_s, text], ...] when the provider gives times


@lru_cache
def _whisper():
    from faster_whisper import WhisperModel  # optional dependency
    return WhisperModel(get_settings().whisper_model, device="auto", compute_type="int8")


def transcribe(path: Path) -> Transcript:
    s = get_settings()
    if s.transcription_provider == "faster_whisper":
        segments, _ = _whisper().transcribe(str(path), vad_filter=True)
        rows = [[round(seg.start, 2), round(seg.end, 2), seg.text.strip()] for seg in segments]
        return Transcript(" ".join(r[2] for r in rows), rows)
    if s.transcription_provider == "parakeet":
        return _parakeet(path)
    if s.transcription_provider == "openai_compatible":
        headers = {"Authorization": f"Bearer {s.transcription_api_key}"} if s.transcription_api_key else {}
        with path.open("rb") as f:
            r = httpx.post(s.transcription_url, headers=headers, timeout=300,
                           files={"file": (path.name, f)}, data={"model": s.whisper_model})
        r.raise_for_status()
        return Transcript(r.json().get("text", ""))
    raise RuntimeError("Transcription is switched off.")


def _rows(data: list) -> list[list]:
    """Parakeet's dataframe output ([[start, end, text], ...] as strings) from the event's data."""
    for item in data or []:
        rows = item.get("data") if isinstance(item, dict) else item
        if isinstance(rows, list) and rows and all(isinstance(r, list) and len(r) >= 3 for r in rows):
            out = []
            for r in rows:
                try:
                    out.append([float(r[0]), float(r[1]), str(r[2]).strip()])
                except (TypeError, ValueError):
                    continue  # the app's own "N/A" placeholder rows
            return out
    return []


def _parakeet(path: Path) -> Transcript:
    """Upload the audio, start transcribe_file, and read its result from the event stream."""
    s = get_settings()
    if not s.parakeet_url:
        raise TranscriptionError("GW_PARAKEET_URL is not set.")
    with httpclient.client("parakeet", base_url=s.parakeet_url.rstrip("/"), timeout=900) as http:
        with path.open("rb") as f:
            r = http.post("/gradio_api/upload", files={"files": (path.name, f)})
        if r.status_code != 200:
            raise TranscriptionError(f"Parakeet refused the audio ({r.status_code}).")
        uploaded = r.json()[0]
        # The second input is the app's session state; over HTTP it is sent empty.
        r = http.post("/gradio_api/call/transcribe_file", json={"data": [
            {"path": uploaded, "orig_name": path.name, "meta": {"_type": "gradio.FileData"}}, None]})
        if r.status_code != 200:
            raise TranscriptionError(f"Parakeet didn't start ({r.status_code}).")
        event_id = r.json()["event_id"]
        event = ""
        with http.stream("GET", f"/gradio_api/call/transcribe_file/{event_id}") as resp:
            for line in resp.iter_lines():
                if line.startswith("event:"):
                    event = line.split(":", 1)[1].strip()
                    jobs.heartbeat()
                elif line.startswith("data:") and event == "complete":
                    rows = _rows(json.loads(line.split(":", 1)[1]))
                    return Transcript(" ".join(r[2] for r in rows if r[2]), rows)
                elif line.startswith("data:") and event == "error":
                    raise TranscriptionError("Parakeet couldn't transcribe this audio.")
    raise TranscriptionError("Parakeet closed the connection without a result.")
