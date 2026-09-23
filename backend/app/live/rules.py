"""Business rules kept out of the diagram, as decision tables.

When staff list conditions ("over a week late, unless they're on a payment plan, and Dean approves
anything over..."), drawing them as a thicket of decision diamonds makes the map unreadable and
duplicates the rules wherever they recur (Real-Life BPMN, section 4.5.4). Instead the map gets one
rule step, and the rules live here in a table: inputs, an outcome, one row per rule.

Values stay as the words staff used. Thresholds are text, not numbers: the decision model is weak
with numbers, and nobody should turn "about a week" into 7 without confirming it.
"""
import uuid

MAX_TABLES, MAX_INPUTS, MAX_ROWS = 30, 12, 80


def _s(v, n=300) -> str:
    return str(v or "").strip()[:n]


def normalise(tables, element_ids: set[str] | None = None) -> list[dict]:
    out = []
    for t in (tables or [])[:MAX_TABLES]:
        if not isinstance(t, dict) or not _s(t.get("name")):
            continue
        inputs = [_s(i, 120) for i in (t.get("inputs") or []) if _s(i, 120)][:MAX_INPUTS]
        rows = []
        for r in (t.get("rows") or [])[:MAX_ROWS]:
            if not isinstance(r, dict):
                continue
            when = {i: _s((r.get("when") or {}).get(i), 200) for i in inputs}
            then = _s(r.get("then"), 300)
            if then or any(when.values()):
                rows.append({"when": when, "then": then, "source": _s(r.get("source"), 300),
                             "confirmed": bool(r.get("confirmed", False))})
        element = _s(t.get("element_id"), 64)
        out.append({
            "id": _s(t.get("id"), 40) or f"rule-{uuid.uuid4().hex[:8]}",
            "name": _s(t.get("name"), 200),
            "question": _s(t.get("question"), 300),
            "inputs": inputs,
            "output": _s(t.get("output"), 120) or "Outcome",
            "rows": rows,
            "element_id": element if element_ids is None or element in element_ids else "",
            "notes": _s(t.get("notes"), 1000),
        })
    return out


def describe(tables: list[dict] | None) -> str:
    if not tables:
        return "No rule tables yet."
    lines = []
    for t in tables:
        lines.append(f"RULE TABLE {t['id']}: {t['name']} (decides: {t['question'] or '?'}; "
                     f"linked step: {t.get('element_id') or 'none'})")
        lines.append("  inputs: " + ", ".join(t["inputs"]) + f" -> {t['output']}")
        for r in t["rows"]:
            cond = "; ".join(f"{k} = {v}" for k, v in r["when"].items() if v) or "(always)"
            lines.append(f"  - when {cond} then {r['then']}{' [confirmed]' if r['confirmed'] else ''}")
    return "\n".join(lines)
