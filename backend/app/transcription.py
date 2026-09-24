"""Speech to text. Local first: faster-whisper runs on the host (CPU is fine for small.en),
or point openai_compatible at a Whisper server on the inference box over Tailscale."""
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

import httpx

from .config import get_settings


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
    if s.transcription_provider == "openai_compatible":
        headers = {"Authorization": f"Bearer {s.transcription_api_key}"} if s.transcription_api_key else {}
        with path.open("rb") as f:
            r = httpx.post(s.transcription_url, headers=headers, timeout=300,
                           files={"file": (path.name, f)}, data={"model": s.whisper_model})
        r.raise_for_status()
        return Transcript(r.json().get("text", ""))
    raise RuntimeError("Transcription is switched off.")
