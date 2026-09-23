"""Turn a canvas into text a model can reason over, and check its structure.

The canvas is spatial; the model needs structure. This reads BPMN node types, works out which lane
each node sits in from its position, follows sequence and message flows, attaches notes to the
nearest element, and runs the structure checks from Real-Life BPMN's conventions: labelled decision
paths, paired parallel gateways, overview-size limits, rework loops worth asking about.
"""
from collections import defaultdict

TYPE_NAMES = {
    "bpmnStart": "Start event", "bpmnEnd": "End event", "bpmnIntermediate": "Intermediate event",
    "bpmnTask": "Task", "bpmnSubprocess": "Sub-process", "bpmnGateway": "Gateway", "bpmnData": "Data",
    "lane": "Lane", "pool": "Outside party (collapsed pool)", "adhoc": "Unclear area (ad hoc sub-process)",
    "sticky": "Note", "text": "Text", "image": "Image",
    "stakeholder": "Stakeholder", "application": "Application", "workaround": "Workaround", "issue": "Issue",
    "risk": "Risk", "control": "Control", "metric": "Metric", "question": "Open question",
}
CONTEXT_NODES = {"stakeholder", "application", "workaround", "issue", "risk", "control", "metric", "question"}
FLOW_NODES = {"bpmnStart", "bpmnEnd", "bpmnIntermediate", "bpmnTask", "bpmnSubprocess", "bpmnGateway", "bpmnData",
              "adhoc"}
SEQUENCE_NODES = FLOW_NODES - {"bpmnData"}


def _num(v, default: float) -> float:
    try:
        return float(v)
    except (TypeError, ValueError):
        return default


def _abs_positions(nodes: list[dict]) -> dict[str, tuple[float, float, float, float]]:
    """Absolute box of every node. Walks parent chains iteratively and stops at a loop, so a
    malformed map can't recurse without end."""
    by_id = {n.get("id"): n for n in nodes}
    out: dict[str, tuple[float, float, float, float]] = {}
    for n in nodes:
        x = _num((n.get("position") or {}).get("x"), 0)
        y = _num((n.get("position") or {}).get("y"), 0)
        seen = {n.get("id")}
        parent = by_id.get(n.get("parentId") or "")
        while parent is not None and parent.get("id") not in seen:
            seen.add(parent.get("id"))
            x += _num((parent.get("position") or {}).get("x"), 0)
            y += _num((parent.get("position") or {}).get("y"), 0)
            parent = by_id.get(parent.get("parentId") or "")
        measured, style = n.get("measured") or {}, n.get("style") or {}
        w = _num(n.get("width") or measured.get("width") or style.get("width"), 160) or 160
        h = _num(n.get("height") or measured.get("height") or style.get("height"), 60) or 60
        out[str(n.get("id"))] = (x, y, w, h)
    return out


def _label(n: dict) -> str:
    d = n.get("data") or {}
    base = (d.get("label") or "").strip() or "(unlabelled)"
    t = n.get("type")
    if t == "bpmnGateway":
        base += f" [{d.get('gatewayType', 'exclusive')} gateway]"
    if t == "bpmnData":
        base += f" [{d.get('dataKind', 'object')}]"
    if t == "bpmnTask" and d.get("taskKind") and d["taskKind"] != "task":
        base += f" [{'business rule' if d['taskKind'] == 'rule' else d['taskKind']} task]"
    if d.get("tags"):
        base += " {" + ", ".join(d["tags"]) + "}"
    if d.get("system"):
        base += f" (system: {d['system']})"
    return base


def _flow(e: dict) -> str:
    return (e.get("data") or {}).get("flow", "sequence")


def structure_checks(doc: dict, session_pass: str = "detail", rules: list | None = None) -> list[dict]:
    """Findings a facilitator can act on. level: fix (breaks a convention), ask (a question for staff),
    info (worth knowing)."""
    from ..live.vocabulary import OVERVIEW_ARTIFACT_LIMIT, OVERVIEW_FLOW_LIMIT, OVERVIEW_STEP_TARGET
    nodes, edges = doc.get("nodes", []), doc.get("edges", [])
    by_id = {n["id"]: n for n in nodes}
    seq = [e for e in edges if _flow(e) == "sequence" and e.get("source") in by_id and e.get("target") in by_id]
    out_e, in_e = defaultdict(list), defaultdict(list)
    for e in seq:
        out_e[e["source"]].append(e)
        in_e[e["target"]].append(e)
    flow = [n for n in nodes if n.get("type") in SEQUENCE_NODES]
    context = [n for n in nodes if n.get("type") in CONTEXT_NODES]
    linked = {e.get("source") for e in edges} | {e.get("target") for e in edges}
    lab = lambda n: ((n.get("data") or {}).get("label") or "").strip()  # noqa: E731
    found: list[dict] = []

    def add(level, text, ids=()):
        found.append({"level": level, "text": text, "ids": list(ids)})

    if flow and not any(n["type"] == "bpmnStart" for n in flow):
        add("fix", "There is no start event. What sets this work off?")
    if flow and not any(n["type"] == "bpmnEnd" for n in flow):
        add("fix", "There is no end event. How does this work finish, and what is the outcome?")
    orphans = [n for n in flow if n["id"] not in linked]
    if orphans:
        add("fix", "Not connected to anything: " + "; ".join(lab(n) or "(unlabelled)" for n in orphans),
            [n["id"] for n in orphans])
    for n in flow:
        if n["type"] != "bpmnGateway":
            continue
        d = n.get("data") or {}
        outs = out_e[n["id"]]
        if d.get("gatewayType") == "parallel":
            continue
        if len(outs) >= 2:
            unl = [e for e in outs if not (e.get("label") or (e.get("data") or {}).get("label"))]
            if unl:
                add("fix", f"Decision \"{lab(n) or 'unlabelled'}\" has paths without an answer on them. "
                           "Label each path, for example Yes and No.", [n["id"]])
            if lab(n) and not lab(n).endswith("?"):
                add("fix", f"Phrase the decision \"{lab(n)}\" as a question, such as \"Paid in full?\"", [n["id"]])
        elif len(in_e[n["id"]]) < 2:
            add("fix", f"Decision \"{lab(n) or 'unlabelled'}\" needs at least two paths out.", [n["id"]])
    par = [n for n in flow if n["type"] == "bpmnGateway" and (n.get("data") or {}).get("gatewayType") == "parallel"]
    splits = [n for n in par if len(out_e[n["id"]]) > 1]
    joins = [n for n in par if len(in_e[n["id"]]) > 1]
    if len(splits) != len(joins):
        add("fix", f"{len(splits)} parallel split(s) but {len(joins)} parallel join(s). Every split into "
                   "parallel work needs a matching join where the work comes back together.",
            [n["id"] for n in par])

    # Rework loops: edges that return to an element still on the current path from the start.
    # Depth-first with an explicit stack, so a long chain of steps can't exhaust recursion.
    order: dict[str, int] = {}
    seen: set[str] = set()
    back: list[tuple[str, str]] = []
    for s_node in [n for n in flow if n["type"] == "bpmnStart"] or flow[:1]:
        if s_node["id"] in seen:
            continue
        seen.add(s_node["id"])
        order[s_node["id"]] = 0
        stack = [(s_node["id"], 0, iter(out_e[s_node["id"]]))]
        while stack:
            nid, depth, edges_out = stack[-1]
            e = next(edges_out, None)
            if e is None:
                order[nid] = 10 ** 9  # finished: later edges into it are not loops
                stack.pop()
                continue
            t = e["target"]
            if t in order and order[t] <= depth:
                back.append((nid, t))
            elif t not in seen:
                seen.add(t)
                order[t] = depth + 1
                stack.append((t, depth + 1, iter(out_e[t])))
    for a, b in back:
        add("ask", f"Work loops back from \"{lab(by_id[a])}\" to \"{lab(by_id[b])}\". How often does that happen? "
                   "Of every ten cases, how many go through without being sent back?", [a, b])

    if session_pass == "overview":
        steps = [n for n in flow if n["type"] in {"bpmnTask", "bpmnSubprocess"}]
        if len(flow) > OVERVIEW_FLOW_LIMIT:
            add("fix", f"{len(flow)} flow elements. An overview reads at a glance with {OVERVIEW_FLOW_LIMIT} or "
                       "fewer. Group detail into sub-processes, or save it for the detail pass.")
        elif len(steps) > OVERVIEW_STEP_TARGET:
            add("info", f"{len(steps)} steps. Aim for about {OVERVIEW_STEP_TARGET} in the overview.")
        extra = [n for n in nodes if n.get("type") in CONTEXT_NODES | {"sticky", "bpmnData", "pool"}]
        if len(extra) > OVERVIEW_ARTIFACT_LIMIT:
            add("info", f"{len(extra)} notes, documents and parties. The overview stays readable with "
                        f"{OVERVIEW_ARTIFACT_LIMIT} or fewer; hide layers or move them to the detail pass.")
    loose = [n for n in context if n["id"] not in linked]
    if loose:
        add("info", "Not linked to a step: " + "; ".join(lab(n) or "(unlabelled)" for n in loose),
            [n["id"] for n in loose])
    for pnode in [n for n in nodes if n.get("type") == "pool"]:
        if pnode["id"] not in linked:
            add("ask", f"What passes between the business and {lab(pnode) or 'this outside party'}?", [pnode["id"]])
    rule_steps = [n for n in flow if n["type"] == "bpmnTask" and (n.get("data") or {}).get("taskKind") == "rule"]
    covered = {t.get("element_id") for t in (rules or [])}
    for n in rule_steps:
        if n["id"] not in covered:
            add("ask", f"\"{lab(n) or 'Rule step'}\" has no rule table yet. What are the conditions and outcomes?",
                [n["id"]])
    for n in [n for n in nodes if n.get("type") == "adhoc"]:
        add("ask", f"Unclear area \"{lab(n)}\": who could walk us through it?", [n["id"]])
    return found


def describe_board(doc: dict, session_pass: str = "detail", rules: list | None = None) -> str:
    nodes, edges = doc.get("nodes", []), doc.get("edges", [])
    if not nodes:
        return "The map is empty."
    box = _abs_positions(nodes)
    by_id = {n["id"]: n for n in nodes}
    lanes = [n for n in nodes if n.get("type") == "lane"]
    pools = [n for n in nodes if n.get("type") == "pool"]

    def lane_of(nid: str) -> str | None:
        x, y, w, h = box[nid]
        cx, cy = x + w / 2, y + h / 2
        for ln in lanes:
            lx, ly, lw, lh = box[ln["id"]]
            if lx <= cx <= lx + lw and ly <= cy <= ly + lh:
                return (ln.get("data") or {}).get("label") or "Unnamed lane"
        return None

    flow = [n for n in nodes if n.get("type") in FLOW_NODES]
    context = [n for n in nodes if n.get("type") in CONTEXT_NODES]
    lines = ["ELEMENTS (id | type | label | lane):"]
    for n in flow:
        lines.append(f"- {n['id']} | {TYPE_NAMES.get(n['type'], n['type'])} | {_label(n)} | {lane_of(n['id']) or '-'}")
    if lanes:
        lines.append("\nLANES, people and teams inside the business (id | who): " + "; ".join(
            f"{ln['id']} | {(ln.get('data') or {}).get('label') or 'Unnamed lane'}" for ln in lanes))
    if pools:
        lines.append("\nOUTSIDE PARTIES, collapsed pools (id | who): " + "; ".join(
            f"{p['id']} | {(p.get('data') or {}).get('label') or 'Outside party'}" for p in pools))
    if context:
        lines.append("\nCONTEXT (id | type | label | linked to):")
        for n in context:
            linked = [by_id[e["target"] if e.get("source") == n["id"] else e["source"]] for e in edges
                      if n["id"] in (e.get("source"), e.get("target"))
                      and (e["target"] if e.get("source") == n["id"] else e["source"]) in by_id]
            tags = ", ".join(_label(x) for x in linked) or "-"
            lines.append(f"- {n['id']} | {TYPE_NAMES[n['type']]} | {_label(n)} | {tags}")

    lines.append("\nCONNECTIONS:")
    for e in edges:
        s, t = by_id.get(e.get("source")), by_id.get(e.get("target"))
        if not s or not t:
            continue
        lbl = e.get("label") or (e.get("data") or {}).get("label") or ""
        lines.append(f"- {_label(s)} --{_flow(e)}{(': ' + lbl) if lbl else ''}--> {_label(t)}")

    checks = structure_checks(doc, session_pass, rules)
    lines.append("\nSTRUCTURE CHECKS:")
    lines.extend(f"- [{c['level']}] {c['text']}" for c in checks) if checks else lines.append("- none")

    notes = [n for n in nodes if n.get("type") in {"sticky", "text"}]
    if notes:
        lines.append("\nNOTES ON THE MAP (with the nearest element):")
        for n in notes:
            x, y, w, h = box[n["id"]]
            near = min(flow, key=lambda f: (box[f["id"]][0] - x) ** 2 + (box[f["id"]][1] - y) ** 2, default=None)
            text = ((n.get("data") or {}).get("label") or "").strip()
            if text:
                lines.append(f"- {n['id']} | \"{text}\" near {_label(near) if near else 'nothing'}")
    return "\n".join(lines)
