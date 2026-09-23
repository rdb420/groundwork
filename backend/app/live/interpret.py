"""Turn one finished sentence into proposed map changes.

One request per sentence asks every question at once (TypeSafe's "speculative fan-out" pattern):
what kind of change, whether it is a step or context, which step or context kind, which existing
element it relates to, who does it, which phrase is the label, and several yes/no checks. Code then
decides what to do with the answers. The model never places anything; it only picks from options
code gave it.

Two passes, following Real-Life BPMN (ch. 3): the overview pass records the standard path only and
sends problems, exceptions, workarounds and rules to the parking lot. The detail pass puts
everything on the map.
"""
import uuid

from ..ai.context import _abs_positions
from ..config import get_settings
from . import jev
from .spans import actor_candidates, candidates
from .vocabulary import CONTEXT_KINDS, FLOW_KINDS, OVERVIEW_FLOW, PARKING_FOR_KIND, kind_of

ACTIONS = {
    "add": "`latest` describes something about the work that is not on the map yet: a step, decision, "
           "person, outside party, system, document, problem, workaround, rule, number or open question",
    "update": "`latest` corrects or adds detail to something already on the map: a better name, a "
              "different kind of element, or a different person or team doing it",
    "connect": "`latest` says two things already on the map happen one after the other or are linked",
    "remove": "`latest` says something on the map does not happen, is wrong, or should be taken off",
    "nothing": "Small talk, a question from the interviewer, agreement, repetition, or nothing new about the work",
}
UPDATE_WHAT = {
    "name": "What the element is called or what it says",
    "kind": "What sort of element it is, for example a step that is really a decision",
    "who": "Which person, role, team or outside party does it",
    "none": "Nothing about an existing element changes",
}
GROUP = {
    "step": "Part of the sequence of work: something done, decided, waited for, or how it starts or ends",
    "context": "Something about the work rather than a step: who is involved, a system, a document, "
               "a problem, a workaround, a risk, a check, a number or something unclear",
}


def _elements(doc: dict, last_touched: str | None, limit: int) -> tuple[list[dict], list[dict], list[dict]]:
    nodes = doc.get("nodes", [])
    box = _abs_positions(nodes) if nodes else {}
    lanes = [n for n in nodes if n.get("type") == "lane"]
    pools = [n for n in nodes if n.get("type") == "pool"]

    def lane_of(nid):
        x, y, w, h = box[nid]
        cx, cy = x + w / 2, y + h / 2
        for ln in lanes:
            lx, ly, lw, lh = box[ln["id"]]
            if lx <= cx <= lx + lw and ly <= cy <= ly + lh:
                return ln
        return None

    items = [n for n in nodes if n.get("type") not in {"lane", "image", "pool"}]
    items = items[::-1]  # newest first; the canvas appends
    if last_touched:
        items.sort(key=lambda n: n["id"] != last_touched)
    out = []
    for n in items[:limit]:
        ln = lane_of(n["id"])
        out.append({"id": n["id"], "kind": kind_of(n), "label": ((n.get("data") or {}).get("label") or "").strip(),
                    "lane": ((ln.get("data") or {}).get("label") if ln else "") or ""})
    label = lambda n, d: ((n.get("data") or {}).get("label") or d)  # noqa: E731
    return (out, [{"id": ln["id"], "label": label(ln, "Unnamed lane")} for ln in lanes],
            [{"id": p["id"], "label": label(p, "Outside party")} for p in pools])


def build_request(text: str, recent: list[str], doc: dict, last_touched: str | None,
                  session_pass: str = "detail") -> tuple[dict, dict, dict]:
    s = get_settings()
    cap = s.decision_max_options
    elements, lanes, pools = _elements(doc, last_touched, cap - 1)
    spans = candidates(text, cap - 1)
    state = {
        "latest": text,
        "said_just_before": recent[-3:],
        "map": {"elements": [{k: e[k] for k in ("kind", "label", "lane")} | {"ref": e["id"]} for e in elements],
                "lanes": [ln["label"] for ln in lanes], "outside_parties": [p["label"] for p in pools]},
        "last_changed_element": next((e["label"] for e in elements if e["id"] == last_touched), ""),
    }
    el_opts = {e["id"]: f"{e['label'] or '(unnamed)'} ({e['kind'].replace('_', ' ')}"
               + (f", in lane {e['lane']})" if e["lane"] else ")") for e in elements}
    el_opts["none"] = "None of these elements"
    who = {ln["id"]: f"{ln['label']} (inside the business)" for ln in lanes[: cap - 3]}
    for p in pools[: max(0, cap - 3 - len(who))]:
        who[p["id"]] = f"{p['label']} (outside party)"
    who["new_lane"] = "A person, role or team inside the business that is not on the map yet"
    who["outside_party"] = "An outside person or organisation not on the map yet: tenant, borrower, owner, " \
                           "bank, contractor, council, government agency"
    who["not_stated"] = "`latest` doesn't say who"
    span_opts = {f"s{i}": sp for i, sp in enumerate(spans)}
    span_opts["none"] = "None of these phrases works"
    actor_opts = {f"a{i}": sp for i, sp in enumerate(actor_candidates(text, cap - 1))}
    actor_opts["none"] = "`latest` doesn't name anyone"
    flow_opts = {k: d for k, d in FLOW_KINDS.items() if session_pass == "detail" or k in OVERVIEW_FLOW}

    q = {
        "directed": jev.noul("Is `latest` an instruction to change the process map, such as add, rename, move, "
                             "connect or remove something on it, rather than a description of the work?"),
        "action": jev.choice("What should change on the process map because of `latest`?", ACTIONS),
        "group": jev.choice("Is what `latest` is about a step in the work, or context about the work?", GROUP),
        "flow_kind": jev.choice("If `latest` is about a step, what sort of step is it?", flow_opts),
        "context_kind": jev.choice("If `latest` is about context rather than a step, what sort is it?", CONTEXT_KINDS),
        "target": jev.choice("Which element already on the map is `latest` about, or does the new thing come "
                             "straight after? If `latest` says 'that' or 'it', it usually means "
                             "`last_changed_element`.", el_opts),
        "other": jev.choice("If `latest` links two elements already on the map, which element is the second one?",
                            el_opts),
        "update_what": jev.choice("If `latest` changes an element already on the map, what changes?", UPDATE_WHAT),
        "who": jev.choice("Who does the work or is involved in `latest`?", who),
        "label": jev.choice("Which phrase from `latest` best names the thing being added or renamed? For a step, "
                            "prefer a phrase that starts with what is done, such as 'check bank feed'.", span_opts),
        "actor": jev.choice("Which word or short phrase from `latest` names the person, role, team or organisation "
                            "involved?", actor_opts),
        "compound": jev.noul("Does `latest` describe two or more separate steps or changes?"),
        "workaround": jev.noul("Does `latest` mention a workaround, such as a side spreadsheet, a copy-paste "
                               "routine, a reminder note or re-typing information?"),
        "issue": jev.noul("Does `latest` mention an error, delay, complaint or something that goes wrong?"),
        "exception": jev.noul("Does `latest` describe what happens only sometimes, an exception, or work being "
                              "sent back to be redone, rather than the usual path?"),
        "states_rule": jev.noul("Does `latest` state a rule or condition that decides what happens, such as a "
                                "threshold, an exception to a rule, or who has to approve?"),
        "from_outside": jev.noul("Does `latest` describe something coming in from an outside party, such as a "
                                 "tenant paying, a bank sending a statement or a contractor calling?"),
        "is_cause": jev.noul("Does `latest` explain why a problem already on the map happens, that is, its cause?"),
    }
    ctx = {"elements": {e["id"]: e for e in elements}, "lanes": {ln["id"]: ln for ln in lanes},
           "pools": {p["id"]: p for p in pools}, "spans": span_opts | actor_opts, "pass": session_pass}
    return state, q, ctx


def _span(ctx, key) -> str:
    return "" if not key or key == "none" else ctx["spans"].get(key, "")


def plan(answers: dict, ctx: dict, mode: str, text: str) -> tuple[list[dict], list[dict], dict]:
    """Code, not the model, decides what happens. Returns (ops, parking, summary)."""
    s = get_settings()
    p = lambda k: jev.prob(answers, k)  # noqa: E731
    directed = p("directed")
    action, a_conf = jev.picked(answers, "action")
    group, g_conf = jev.picked(answers, "group")
    fkind, f_conf = jev.picked(answers, "flow_kind")
    ckind, c_conf = jev.picked(answers, "context_kind")
    target, t_conf = jev.picked(answers, "target")
    other, o_conf = jev.picked(answers, "other")
    what, w_conf = jev.picked(answers, "update_what")
    who, _ = jev.picked(answers, "who")
    label_key, lb_conf = jev.picked(answers, "label")
    actor_key, _ = jev.picked(answers, "actor")
    kind, k_conf = (fkind, f_conf) if group == "step" else (ckind, c_conf)
    summary = {"directed": round(directed, 2), "action": action, "action_conf": round(a_conf, 2), "kind": kind,
               "target": target, "compound": round(p("compound"), 2), "pass": ctx["pass"]}

    heard = text if len(text) <= 160 else text[:157] + "..."
    target = target if target in ctx["elements"] else None
    other = other if other in ctx["elements"] else None
    overview = ctx["pass"] == "overview"
    parking: list[dict] = []

    def park(category):
        if category not in {x["category"] for x in parking}:
            parking.append({"category": category, "text": text, "near_element": target or ""})

    # Rules are captured in both passes: they feed the rule tables, not the diagram.
    if p("states_rule") > 0.6:
        park("rule")

    if mode == "command" and directed < 0.5:
        return [], parking, summary
    if action in (None, "nothing"):
        return [], parking, summary

    if overview:
        # Keep the standard path clean. Everything else waits for the detail pass.
        for flag, cat in (("issue", "issue"), ("workaround", "workaround"), ("exception", "exception")):
            if p(flag) > 0.7:
                park(cat)
        if action == "add" and (group != "step" or kind not in OVERVIEW_FLOW or p("exception") > 0.7):
            park(PARKING_FOR_KIND.get(kind, "detail"))
            return [], parking, summary

    label = _span(ctx, label_key)
    actor = _span(ctx, actor_key)
    who_fields = {}
    if who in ctx["lanes"]:
        who_fields = {"lane_id": who}
    elif who in ctx["pools"]:
        who_fields = {"party": ctx["pools"][who]["label"]}
    elif who == "new_lane" and actor:
        who_fields = {"new_lane": actor}
    elif who == "outside_party" and actor:
        who_fields = {"party": actor}

    threshold = s.live_auto_threshold * (0.85 if directed >= 0.5 else 1.0)  # direct instructions need less
    ops: list[dict] = []

    if action == "add" and kind in FLOW_KINDS | CONTEXT_KINDS:
        conf = min(a_conf, g_conf, k_conf, lb_conf if label else 0.5)
        if kind == "external_party":
            # An outside party is a collapsed pool; the element it touches gets a message flow.
            name = actor or label
            if name:
                ops.append({"op": "add", "ref": f"n{uuid.uuid4().hex[:8]}", "kind": "external_party", "label": name,
                            "after": target, "direction": "in" if p("from_outside") > 0.5 else "out",
                            "confidence": round(min(conf, 0.99), 2)})
        else:
            tags = [t for t in ("workaround", "issue") if p(t) > 0.7 and kind != t]
            op = {"op": "add", "ref": f"n{uuid.uuid4().hex[:8]}", "kind": kind, "label": label, "after": target,
                  "tags": tags, **who_fields}
            if "party" in who_fields:
                op["direction"] = "in" if p("from_outside") > 0.5 else "out"
            if kind == "issue" and target and ctx["elements"][target]["kind"] == "issue" and p("is_cause") > 0.6:
                op["relation"] = "cause"  # this issue explains the one it points at
            ops.append(op | {"confidence": round(conf, 2)})
    elif action == "update" and target:
        changes = {}
        if what == "name" and label:
            changes["label"] = label
        elif what == "kind" and kind in FLOW_KINDS | CONTEXT_KINDS and kind != ctx["elements"][target]["kind"] \
                and kind != "external_party":
            changes["kind"] = kind
        elif what == "who" and who_fields and "party" not in who_fields:
            changes.update(who_fields)
        if changes:
            ops.append({"op": "update", "target": target, "changes": changes,
                        "confidence": round(min(a_conf, t_conf, w_conf), 2)})
    elif action == "connect" and target and other and target != other:
        ops.append({"op": "connect", "from": target, "to": other, "confidence": round(min(a_conf, t_conf, o_conf), 2)})
    elif action == "remove" and target:
        ops.append({"op": "remove", "target": target, "confidence": round(min(a_conf, t_conf), 2)})

    for op in ops:
        op["id"] = f"op{uuid.uuid4().hex[:10]}"
        op["source"] = "jev"
        op["reason"] = f"Heard: \"{heard}\""
        op["auto"] = op["op"] != "remove" and op["confidence"] >= threshold
    return ops, parking, summary
