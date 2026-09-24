"""Client for the System One endpoint. The same request works against OpenRouter's System One API
(GW_DECISION_PROVIDER=openrouter, the default route for Jev), TypeSafe's own endpoint, and
Jev-compatible servers you run yourself (Laya, OpenJev), so switching is a configuration change.

Portability notes, from each project's README at the time of writing:
- OpenJev caps a Choice at 128 options and rejects pinned Jev version names; use an alias.
- Laya's accuracy drops when a Choice has many options, so questions here stay at or under
  GW_DECISION_MAX_OPTIONS (default 20).
"""
import time
from dataclasses import dataclass, field
from typing import Any

import httpx

from ..config import get_settings


class DecisionError(RuntimeError):
    pass


@dataclass
class Target:
    """Where a decision request goes and how to phrase it.

    flavour "jev": TypeSafe Jev (hosted, or through OpenRouter) and OpenJev.
    flavour "laya": Laya (convaiinnovations/laya, self-hosted). Same API, but its English checkpoint
    leans to "no" on yes/no questions when their options are labelled true/false, so those go out
    with neutral labels, and option text shares a 192-token budget, so callers keep options short.
    """
    url: str
    headers: dict[str, str] = field(default_factory=dict)
    model: str = ""
    flavour: str = "jev"
    local: bool = False


def live_target() -> Target:
    """The decision model live mapping uses."""
    s = get_settings()
    url, headers = endpoint()
    return Target(url, headers, s.decision_model, s.decision_flavour, s.decision_local)


def for_flavour(questions: dict, flavour: str) -> dict:
    if flavour != "laya":
        return questions
    out = {}
    for key, q in questions.items():
        if q.get("type") == "noul":
            q = {**q, "criteria": q.get("criteria") or {"true": "yes, it does", "false": "no, it doesn't"},
                 "labels": {"true": "A", "false": "B"}}
        out[key] = q
    return out


def system_one(state, questions: dict, *, target: Target | None = None) -> tuple[dict, str, int]:
    """Returns (answers, model, latency_ms). target overrides the live-mapping decision model."""
    target = target or live_target()
    url, headers = target.url, target.headers
    body = {"model": target.model, "state": state, "questions": for_flavour(questions, target.flavour)}
    t0 = time.perf_counter()
    for attempt in range(3):
        try:
            r = httpx.post(url, json=body, headers=headers, timeout=get_settings().decision_timeout_s)
        except httpx.HTTPError as e:
            raise DecisionError(f"Couldn't reach the decision model: {e}") from e
        if r.status_code == 429 and attempt < 2:
            time.sleep(float(r.headers.get("retry-after", 1)))
            continue
        break
    if r.status_code >= 400:
        raise DecisionError(f"Decision model returned {r.status_code}: {r.text[:300]}")
    data = r.json()
    return data.get("answers", {}), data.get("model", target.model), int((time.perf_counter() - t0) * 1000)


def endpoint() -> tuple[str, dict[str, str]]:
    """URL and headers for the configured provider."""
    s = get_settings()
    if s.decision_provider == "openrouter":
        if not s.openrouter_api_key:
            raise DecisionError("GW_OPENROUTER_API_KEY is not set. Add it to .env and restart.")
        # X-Title and HTTP-Referer are OpenRouter's optional app attribution headers.
        return s.openrouter_url, {"Authorization": f"Bearer {s.openrouter_api_key}", "X-Title": s.app_name,
                                  "HTTP-Referer": s.public_base_url}
    if s.decision_provider == "jev":
        return s.decision_url, {"Authorization": f"Bearer {s.decision_api_key}"} if s.decision_api_key else {}
    raise DecisionError("Live mapping is switched off. Set GW_DECISION_PROVIDER to openrouter or jev.")


def noul(q: str, true: str | None = None, false: str | None = None) -> dict:
    out: dict[str, Any] = {"type": "noul", "instructions": q}
    if true or false:
        out["criteria"] = {"true": true or "Yes", "false": false or "No"}
    return out


def choice(q, options: dict) -> dict:
    return {"type": "choice", "instructions": q, "criteria": options}


def picked(answers: dict, key: str) -> tuple[str | None, float]:
    """(choice, confidence) for a Choice answer; (None, 0) if missing. Laya reports the chosen
    option's calibrated probability as answer_confidence (its `confidence` is an uncalibrated
    entropy measure for choices), which is what Jev's `confidence` means, so prefer it."""
    a = answers.get(key) or {}
    return a.get("choice"), float(a.get("answer_confidence", a.get("confidence", 0.0)))


def prob(answers: dict, key: str) -> float:
    return float((answers.get(key) or {}).get("noul", 0.0))
