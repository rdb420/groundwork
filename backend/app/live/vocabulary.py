"""What can go on a map. One list drives the decision-model questions, the reviewer prompt,
validation of every proposed change, and (mirrored in frontend/src/canvas/kinds.ts) the canvas.

Flow kinds sit in the sequence of work and connect with sequence flows. Context kinds describe
something about the work (who, which system, what goes wrong) and attach with a dotted link.
Outside parties are collapsed pools and connect with message flows.

The two groups are asked as separate questions so no Choice has more than 20 options, which
keeps the questions portable to Laya and OpenJev.
"""

FLOW_KINDS: dict[str, str] = {
    "start": "What sets the work off, such as a request, a date or a message arriving",
    "task": "A step someone does",
    "manual_task": "A step done by hand: paper, phone calls, re-typing or copying between files",
    "system_task": "A step a system or software does by itself",
    "rule_task": "A step where a decision is made by applying rules or conditions, such as thresholds, "
                 "exceptions or who has to approve",
    "subprocess": "A bigger chunk of work made of several steps, such as arrears follow-up",
    "decision": "A point where the work goes one way or another depending on the answer to a question",
    "parallel": "A point where two or more things happen at the same time",
    "wait": "Waiting for something: a reply, a payment, a date or another person",
    "end": "How the work finishes: the outcome",
}

CONTEXT_KINDS: dict[str, str] = {
    "external_party": "An outside person or organisation the work deals with: tenant, borrower, owner, bank, "
                      "contractor, council, government agency",
    "stakeholder": "Someone inside the business who has an interest or is mentioned, without doing a step here",
    "application": "A software system or app used: Xero, a bank portal, property software, email",
    "document": "A document, form, report, template or file used or produced",
    "workaround": "Something staff do to get around a gap: a side spreadsheet, a reminder note, a copy-paste routine",
    "issue": "An error, problem, delay, complaint or pain point",
    "risk": "Something that could go wrong with serious consequences: legal, financial, safety or compliance",
    "control": "A check, approval, sign-off or rule that must be followed",
    "metric": "A number about the work: how often, how many, how long, how much, how often it is redone",
    "question": "Something unknown that needs confirming later",
    "unclear": "A part of the work nobody can yet describe as clear steps in order",
    "note": "Any other remark worth keeping on the map",
}

KINDS: dict[str, dict] = {k: {"group": "flow", "desc": d} for k, d in FLOW_KINDS.items()} | \
                         {k: {"group": "context", "desc": d} for k, d in CONTEXT_KINDS.items()}
FLOW = set(FLOW_KINDS)
CONTEXT = set(CONTEXT_KINDS)

# The overview pass records the standard path only (Freund and Rucker, Real-Life BPMN, ch. 3):
# start to end, about eight steps, usual responsibilities, no weak points or improvements.
OVERVIEW_FLOW = {"start", "task", "subprocess", "decision", "end"}
OVERVIEW_STEP_TARGET = 8
OVERVIEW_FLOW_LIMIT = 10
OVERVIEW_ARTIFACT_LIMIT = 8

# Where things heard during the overview pass wait until the detail pass.
PARKING_FOR_KIND = {
    "issue": "issue", "risk": "issue", "workaround": "workaround", "control": "rule", "rule_task": "rule",
    "question": "question", "unclear": "question", "parallel": "exception", "wait": "exception",
}
PARKING_CATEGORIES = {"issue", "workaround", "exception", "rule", "question", "detail"}

# How each kind is stored on the canvas: React Flow node type plus data defaults.
NODE_FOR_KIND: dict[str, tuple[str, dict]] = {
    "start": ("bpmnStart", {}), "end": ("bpmnEnd", {}), "wait": ("bpmnIntermediate", {}),
    "task": ("bpmnTask", {}), "manual_task": ("bpmnTask", {"taskKind": "manual"}),
    "system_task": ("bpmnTask", {"taskKind": "system"}), "rule_task": ("bpmnTask", {"taskKind": "rule"}),
    "subprocess": ("bpmnSubprocess", {}),
    "decision": ("bpmnGateway", {"gatewayType": "exclusive"}),
    "parallel": ("bpmnGateway", {"gatewayType": "parallel"}),
    "document": ("bpmnData", {"dataKind": "object"}),
    "external_party": ("pool", {}), "unclear": ("adhoc", {}),
    "stakeholder": ("stakeholder", {}), "application": ("application", {}), "workaround": ("workaround", {}),
    "issue": ("issue", {}), "risk": ("risk", {}), "control": ("control", {}), "metric": ("metric", {}),
    "question": ("question", {}), "note": ("sticky", {}),
}


def kind_of(node: dict) -> str:
    """Reverse of NODE_FOR_KIND for a saved canvas node."""
    t, d = node.get("type"), node.get("data") or {}
    if t == "bpmnTask":
        return {"manual": "manual_task", "system": "system_task", "rule": "rule_task"}.get(d.get("taskKind", ""), "task")
    if t == "bpmnGateway":
        return "parallel" if d.get("gatewayType") == "parallel" else "decision"
    if t == "bpmnData":
        return "document"
    for k, (nt, _) in NODE_FOR_KIND.items():
        if nt == t:
            return k
    return {"sticky": "note", "text": "note"}.get(t, "note")
