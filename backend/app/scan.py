"""Malware scanning with ClamAV's clamd daemon over TCP (the INSTREAM command). No client library:
the protocol is a few lines. Groundwork never opens or runs uploaded files, but staff download
them, so a flagged file is quarantined and can't be downloaded."""
import socket
import struct
from pathlib import Path

from .config import get_settings

CHUNK = 1024 * 1024


class ScannerUnavailable(RuntimeError):
    pass


def enabled() -> bool:
    return bool(get_settings().clamav_host)


def scan_file(path: Path) -> str | None:
    """Returns the signature name if clamd flags the file, None if it is clean."""
    s = get_settings()
    try:
        with socket.create_connection((s.clamav_host, s.clamav_port), timeout=120) as sock:
            sock.sendall(b"zINSTREAM\0")
            with path.open("rb") as f:
                while chunk := f.read(CHUNK):
                    sock.sendall(struct.pack("!L", len(chunk)) + chunk)
            sock.sendall(struct.pack("!L", 0))
            reply = b""
            while not reply.endswith(b"\0"):
                part = sock.recv(4096)
                if not part:
                    break
                reply += part
    except OSError as e:
        raise ScannerUnavailable(f"Couldn't reach the malware scanner at {s.clamav_host}:{s.clamav_port}: {e}") from e
    text = reply.rstrip(b"\0").decode(errors="replace")
    if text.endswith("FOUND"):
        return text.removeprefix("stream:").removesuffix("FOUND").strip() or "unknown"
    if text.endswith("OK"):
        return None
    raise ScannerUnavailable(f"The malware scanner gave an unexpected answer: {text[:200]}")
