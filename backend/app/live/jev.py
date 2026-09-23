"""Client for the System One endpoint. The same request works against TypeSafe's hosted Jev and
against Jev-compatible servers you run yourself (Laya, OpenJev), so moving off the hosted API
is a change of GW_DECISION_URL and GW_DECISION_MODEL.

Portability notes, from each project's README at the time of writing:
- OpenJev caps a Choice at 128 options and rejects pinned Jev version names; use an alias.
- Laya's accuracy drops when a Choice has many options, so questions here stay at or under
  GW_DECISION_MAX_OPTIONS (default 20).
"""
import time

import httpx

from ..config import get_settings


class DecisionError(RuntimeError):
    pass


def system_one(state, questions: dict) -> tuple[dict, str, int]:
    """Returns (answers, model, latency_ms)."""
    s = get_settings()
    if s.decision_provider == "none":
        raise DecisionError("Live mapping is switched off. Set GW_DECISION_PROVIDER=jev.")
    headers = {"Authorization": f"Bearer {s.decision_api_key}"} if s.decision_api_key else {}
    body = {"model": s.decision_model, "state": state, "questions": questions}
    t0 = time.perf_counter()
    for attempt in range(3):
        try:
            r = httpx.post(s.decision_url, json=body, headers=headers, timeout=15)
        except httpx.HTTPError as e:
            raise DecisionError(f"Couldn't reach the decision model: {e}") from e
        if r.status_code == 429 and attempt < 2:
            time.sleep(float(r.headers.get("retry-after", 1)))
            continue
        break
    if r.status_code >= 400:
        raise DecisionError(f"Decision model returned {r.status_code}: {r.text[:300]}")
    data = r.json()
    return data.get("answers", {}), data.get("model", s.decision_model), int((time.perf_counter() - t0) * 1000)


def noul(q: str, true: str | None = None, false: str | None = None) -> dict:
    out = {"type": "noul", "instructions": q}
    if true or false:
        out["criteria"] = {"true": true or "Yes", "false": false or "No"}
    return out


def choice(q, options: dict) -> dict:
    return {"type": "choice", "instructions": q, "criteria": options}


def picked(answers: dict, key: str) -> tuple[str | None, float]:
    """(choice, confidence) for a Choice answer; (None, 0) if missing."""
    a = answers.get(key) or {}
    return a.get("choice"), float(a.get("confidence", 0.0))


def prob(answers: dict, key: str) -> float:
    return float((answers.get(key) or {}).get("noul", 0.0))
