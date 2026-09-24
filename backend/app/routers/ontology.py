"""Terms the documents use that the ontology doesn't have yet. The pipeline proposes them; an
analyst accepts, merges into an existing term, or rejects each one. Accepted proposals are exported
as a change for property_ontology's build script (build/build_model.py); Groundwork never edits the
ontology itself, and a new version only takes effect once it is vendored and pinned."""
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session as DB

from .. import audit
from ..db import get_db
from ..ingest.ontology import load
from ..models import Artifact, Board, Chunk, Document, OntologyCandidate, Recording, User
from ..security import require, utcnow
from ..util import get_or_404

router = APIRouter(prefix="/api/ontology", tags=["ontology"])
ACTIONS = {"accept": "accepted", "reject": "rejected", "merge": "merged", "reopen": "open"}


class Decision(BaseModel):
    action: str
    merged_into_iri: str = ""
    parent_iri: str = ""
    label: str = Field("", max_length=300)
    note: str = Field("", max_length=2000)


def _evidence(db: DB, chunk_ids: list[str]) -> list[dict]:
    out = []
    for c in db.scalars(select(Chunk).where(Chunk.id.in_(chunk_ids or []))).all():
        doc = db.get(Document, c.document_id)
        title = ""
        if c.source_type == "artifact":
            a = db.get(Artifact, c.source_id)
            title = a.title if a else ""
        else:
            rec = db.get(Recording, c.source_id)
            board = db.get(Board, rec.board_id) if rec else None
            title = f"Session: {board.title}" if board else "Session"
        out.append({"chunk_id": c.id, "text": c.text[:400], "title": title, "source_type": c.source_type,
                    "source_id": c.source_id, "page": c.page, "start_s": c.start_s,
                    "personal_info": bool(doc and doc.personal_info)})
    return out


def _dict(db: DB, c: OntologyCandidate, with_evidence: bool = True) -> dict:
    o = load(c.ontology_version) if c.ontology_version else load()
    d = {"id": c.id, "kind": c.kind, "label": c.label, "occurrences": c.occurrences, "status": c.status,
         "domain": {"iri": c.domain_iri, "label": o.label(c.domain_iri)} if c.domain_iri else None,
         "range": {"iri": c.range_iri, "label": o.label(c.range_iri)} if c.range_iri else None,
         "parent_iri": c.parent_iri, "merged_into_iri": c.merged_into_iri, "note": c.note,
         "ontology_version": c.ontology_version, "created_at": c.created_at, "decided_at": c.decided_at}
    if with_evidence:
        d["evidence"] = _evidence(db, (c.evidence or [])[:5])
    return d


@router.get("/candidates")
def candidates(status: str = "open", user: User = Depends(require("analyst")), db: DB = Depends(get_db)):
    rows = db.scalars(select(OntologyCandidate).where(OntologyCandidate.status == status)
                      .order_by(OntologyCandidate.occurrences.desc(), OntologyCandidate.created_at)).all()
    return [_dict(db, c) for c in rows[:200]]


@router.get("/terms")
def terms(q: str = "", user: User = Depends(require("analyst"))):
    """Existing classes, properties and concepts, to merge a candidate into."""
    o = load()
    q = q.casefold().strip()
    items = ([{"iri": i, "kind": "class", "label": o.label(i)} for i in o.classes]
             + [{"iri": i, "kind": "relation", "label": o.label(i)} for i in o.properties]
             + [{"iri": c["iri"], "kind": "concept", "label": c["label"]} for cs in o.concepts.values() for c in cs])
    return sorted([t for t in items if not q or q in t["label"].casefold()], key=lambda t: t["label"])[:50]


@router.post("/candidates/{cid}")
def decide(cid: str, body: Decision, request: Request, user: User = Depends(require("analyst")),
           db: DB = Depends(get_db)):
    c = get_or_404(db, OntologyCandidate, cid, "Proposal")
    if body.action not in ACTIONS:
        raise HTTPException(422, "Choose accept, merge, reject or reopen.")
    if c.status == "exported" and body.action != "reopen":
        raise HTTPException(409, "This proposal has already been exported to the ontology.")
    o = load()
    if body.action == "merge":
        known = set(o.classes) | set(o.properties) | {x["iri"] for cs in o.concepts.values() for x in cs}
        if body.merged_into_iri not in known:
            raise HTTPException(422, "Choose an existing term to merge into.")
        c.merged_into_iri = body.merged_into_iri
    if body.parent_iri:
        if body.parent_iri not in o.classes:
            raise HTTPException(422, "Choose an existing class as the parent.")
        c.parent_iri = body.parent_iri
    if body.label.strip():
        c.label = body.label.strip()
    c.status, c.note = ACTIONS[body.action], body.note.strip()
    c.decided_by, c.decided_at = (None, None) if body.action == "reopen" else (user.id, utcnow())
    audit.record(db, f"ontology.candidate_{c.status}", "ontology_candidate", cid, actor_id=user.id, request=request,
                 detail={"kind": c.kind, "label": c.label, "merged_into": c.merged_into_iri, "parent": c.parent_iri})
    db.commit()
    return _dict(db, c, with_evidence=False)


def _slug(label: str) -> str:
    words = "".join(ch if ch.isalnum() else " " for ch in label).split()
    return "".join(w[:1].upper() + w[1:] for w in words) or "Unnamed"


@router.post("/candidates-export")
def export(request: Request, user: User = Depends(require("analyst")), db: DB = Depends(get_db)):
    """Accepted and merged proposals as a change for property_ontology: a Markdown summary for the
    decision log and YAML term entries for build_model.py. Marks them exported."""
    rows = db.scalars(select(OntologyCandidate).where(OntologyCandidate.status.in_(("accepted", "merged")))
                      .order_by(OntologyCandidate.kind, OntologyCandidate.label)).all()
    if not rows:
        raise HTTPException(409, "Nothing has been accepted since the last export.")
    o = load()
    md = [f"# Proposed changes to property_ontology {o.version}", "",
          f"From Groundwork, {utcnow():%d %B %Y}. Each item cites the documents it came from.", ""]
    yaml_lines = ["# Paste into build/build_model.py's term list and review before building.", "terms:"]
    for c in rows:
        evidence = _evidence(db, (c.evidence or [])[:3])
        where = "; ".join(f"\"{e['title']}\"" + (f" p.{e['page']}" if e["page"] else "") for e in evidence)
        if c.status == "merged":
            md.append(f"- **{c.label}** ({c.kind}): use existing `{c.merged_into_iri}` ({o.label(c.merged_into_iri)}) "
                      f"as an alternative label. Seen {c.occurrences} times: {where}.")
            continue
        iri = f"pbo:{_slug(c.label)}" if c.kind != "relation" else f"pbo:{_slug(c.label)[:1].lower()}{_slug(c.label)[1:]}"
        md.append(f"- **{c.label}** (new {c.kind}, `{iri}`)"
                  + (f", under `{c.parent_iri}`" if c.parent_iri else "")
                  + (f", from {o.label(c.domain_iri)} to {o.label(c.range_iri)}" if c.domain_iri else "")
                  + f". Seen {c.occurrences} times: {where}." + (f" Note: {c.note}" if c.note else ""))
        kind = {"class": "class", "relation": "object_property", "concept": "skos_concept"}[c.kind]
        yaml_lines += [f"- id: TERM-{iri.split(':')[1]}", f"  iri: {iri}", f"  kind: {kind}",
                       f"  label: {c.label!r}", "  definition: TODO", "  status: proposed",
                       "  support: source_supported", f"  rationale: {('Groundwork: ' + c.note)!r}"]
        if c.kind == "relation":
            yaml_lines += [f"  domain: {c.domain_iri or 'null'}", f"  range: {c.range_iri or 'null'}"]
        if c.parent_iri:
            yaml_lines.append(f"  # subClassOf {c.parent_iri}")
    for c in rows:
        c.status = "exported"
    audit.record(db, "ontology.candidates_exported", "ontology_candidate", actor_id=user.id, request=request,
                 detail={"count": len(rows), "ontology_version": o.version})
    db.commit()
    return {"markdown": "\n".join(md) + "\n", "yaml": "\n".join(yaml_lines) + "\n", "count": len(rows)}
