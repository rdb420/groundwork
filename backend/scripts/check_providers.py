"""Check every configured service answers, after you put URLs and keys in .env.

    cd backend && uv run python -m scripts.check_providers

Covers the AI models (decision and drafting), file storage, and the ingestion pipeline's services:
MinerU, Gotenberg, Parakeet, the embedding and extraction sidecars, Qdrant and Neo4j. Sends no
map, transcript or file content: at most one made-up sentence to the models.
"""
import time
import uuid

from app import httpclient
from app.ai.providers import ProviderError, complete
from app.config import get_settings
from app.ingest import tokens
from app.live import jev

OK, FAIL = "ok", "failed"


def line(name: str, status: str, detail: str = "") -> bool:
    print(f"{name:<22} {status:<7} {detail}")
    return status != FAIL


def get(name: str, url: str, path: str, **kw) -> tuple[bool, str]:
    try:
        with httpclient.client(name, base_url=url.rstrip("/"), timeout=15, **kw) as http:
            r = http.get(path)
        return r.status_code < 400, f"HTTP {r.status_code}"
    except Exception as e:  # report and carry on to the next service
        return False, type(e).__name__


def main() -> int:
    s = get_settings()
    ok = True
    if s.decision_provider != "none":
        try:
            answers, model, ms = jev.system_one({"latest": "I check the bank feed every morning."},
                                                {"step": jev.noul("Does `latest` describe a step in the work?")})
            ok &= line("Decision model", OK, f"{model} answered {answers.get('step')} in {ms} ms")
        except jev.DecisionError as e:
            ok &= line("Decision model", FAIL, str(e))
    if s.ai_provider != "none":
        t0 = time.perf_counter()
        try:
            text, provider, model = complete("Reply with one JSON object and nothing else.", 'Return {"ok": true}.')
            ok &= line("Drafting model", OK, f"{provider} {model} replied {text.strip()[:40]!r} "
                                             f"in {time.perf_counter() - t0:.1f} s")
        except (ProviderError, KeyError) as e:
            ok &= line("Drafting model", FAIL, str(e))

    if s.storage_backend == "s3":
        from app.storage import get_storage
        key = f"artifacts/_check/{uuid.uuid4().hex}.txt"
        try:
            st = get_storage()
            st.put_bytes(key, b"check")
            good = st.read_bytes(key) == b"check"
            st.delete_prefix(key)
            ok &= line("File storage (S3)", OK if good else FAIL, s.s3_endpoint)
        except Exception as e:  # report and carry on
            ok &= line("File storage (S3)", FAIL, f"{type(e).__name__}: {e}")
    else:
        line("File storage", OK, f"local, under {s.data_dir}")

    checks = [
        ("MinerU", s.mineru_url, "mineru", "/health", {}),
        ("Gotenberg", s.gotenberg_url, "gotenberg", "/health", {}),
        ("Parakeet", s.parakeet_url if s.transcription_provider == "parakeet" else "", "parakeet", "/gradio_api/info", {}),
        ("Embedding sidecar", s.embed_url, "embed", "/health", {}),
        ("Extraction sidecar", s.extract_url, "extract", "/health", {}),
        ("Qdrant", s.qdrant_url, "qdrant", "/collections",
         {"headers": {"api-key": s.qdrant_api_key} if s.qdrant_api_key else {},
          "verify": httpclient.verify_option(s.qdrant_ca_file)}),
    ]
    for name, url, client_name, path, kw in checks:
        if not url:
            line(name, "off")
            continue
        good, detail = get(client_name, url, path, **kw)
        ok &= line(name, OK if good else FAIL, detail)
    if s.neo4j_url:
        from app.ingest import graph
        try:
            graph.run([("RETURN 1 AS ok", {})])
            ok &= line("Neo4j", OK, s.neo4j_url)
        except Exception as e:  # report and carry on
            ok &= line("Neo4j", FAIL, f"{type(e).__name__}: {e}")
    else:
        line("Neo4j", "off")

    n = tokens.count("Arrears over 14 days get a breach notice.")
    ok &= line("Tokenizer", OK if n == 11 else FAIL, f"{n} tokens for the check sentence (want 11)")
    print("Pipeline:", "on" if s.pipeline_enabled else "off (GW_PIPELINE_ENABLED=false)")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
