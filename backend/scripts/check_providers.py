"""Check the configured model providers answer, after you put API keys in .env.

    cd backend && uv run python -m scripts.check_providers

Sends one tiny question to the decision model and one short prompt to the drafting model, and
prints what each returned. It sends no map, transcript or file content.
"""
import time

from app.ai.providers import ProviderError, complete
from app.config import get_settings
from app.live import jev


def main() -> int:
    s = get_settings()
    ok = True
    print(f"Decision model: {s.decision_provider} ({s.decision_model})")
    if s.decision_provider != "none":
        try:
            answers, model, ms = jev.system_one({"latest": "I check the bank feed every morning."},
                                                {"step": jev.noul("Does `latest` describe a step in the work?")})
            print(f"  ok: {model} answered {answers.get('step')} in {ms} ms")
        except jev.DecisionError as e:
            ok = False
            print(f"  failed: {e}")
    print(f"Drafting and review model: {s.ai_provider}")
    if s.ai_provider != "none":
        t0 = time.perf_counter()
        try:
            text, provider, model = complete("Reply with one JSON object and nothing else.",
                                             'Return {"ok": true}.')
            print(f"  ok: {provider} {model} replied {text.strip()[:80]!r} in {time.perf_counter() - t0:.1f} s")
        except (ProviderError, KeyError) as e:
            ok = False
            print(f"  failed: {e}")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
