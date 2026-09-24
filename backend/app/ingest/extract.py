"""Entities, chunk tags and relationships for one document, closed to the pinned ontology.

1. GLiNER2 (extraction sidecar) finds spans for each group of ontology classes, with the class
   definitions as label descriptions, plus one catch-all label for named things that fit nowhere.
2. Overlapping spans keep the most confident. When two classes are close for the same span, Jev
   picks from those classes (or none).
3. GLiNER2's classifier tags each chunk with SKOS concepts from the kind schemes.
4. For mention pairs in the same chunk (nearest first), Jev picks the relationship from only the
   ontology properties and roles valid between the two classes, plus "none" and "another
   relationship". More than 18 options become two questions (which group, then which option), so no
   question has more than 20. Arithmetic, counting and option building stay here in code.
5. Catch-all spans and "another relationship" answers become ontology candidates for a person.

Chunk text reaches the decision model as data inside `state`, never as instructions. Files with
personal information (or not sure) only go to a local decision model unless cloud use is allowed;
otherwise their entities are kept and the relationships wait (status "partial").
"""
import hashlib
import logging
from dataclasses import dataclass, field

from sqlalchemy import delete, select
from sqlalchemy.orm import Session as DB

from ..config import get_settings
from ..live import jev
from ..models import Chunk, ChunkTag, Document, EntityMention, OntologyCandidate, RelationAssertion
from . import extractor, resolve
from .ontology import Ontology, Option, load

log = logging.getLogger("groundwork.pipeline")
EXTRACTOR_VERSION = "1"
CATCH_ALL = "other named thing"
CATCH_ALL_DESCRIPTION = ("A named organisation, system, programme, document, place or kind of thing that matters to "
                         "the work but fits none of the other labels")
CLASS_MARGIN = 0.1  # two classes this close for one span go to Jev
# Options per question before it splits in two (plus "none" and "another"). Laya's options share a
# 192-token budget, so it gets fewer, shorter ones.
GROUP_SIZE = {"jev": 18, "laya": 8}


def group_size(flavour: str) -> int:
    return GROUP_SIZE.get(flavour, 18)


@dataclass
class Mention:
    chunk: int
    start: int
    end: int
    text: str
    class_iri: str  # "" for the catch-all
    score: float
    alternatives: list[tuple[str, float]] = field(default_factory=list)
    method: str = "gliner2"
    id: str = ""


def extraction_target() -> jev.Target | None:
    """Extraction's own decision model (for example a local Laya), or the live-mapping one."""
    s = get_settings()
    if s.extract_decision_url:
        headers = {"Authorization": f"Bearer {s.extract_decision_api_key}"} if s.extract_decision_api_key else {}
        return jev.Target(s.extract_decision_url, headers, s.extract_decision_model or s.decision_model,
                          s.extract_decision_flavour or "jev", s.extract_decision_is_local)
    if s.decision_provider != "none":
        try:
            live = jev.live_target()
        except jev.DecisionError:  # set up but missing its key: treat as not set up
            return None
        return jev.Target(live.url, live.headers, s.extract_decision_model or live.model,
                          s.extract_decision_flavour or live.flavour, live.local)
    return None


def decision_target(doc: Document) -> tuple[jev.Target | None, str]:
    """(where relationship questions go, reason they can't go anywhere or "")."""
    s = get_settings()
    target = extraction_target()
    if target is None:
        return None, "No decision model is set up, so relationships weren't extracted."
    if doc.personal_info and not target.local and not s.ai_allow_cloud_for_personal_info:
        return None, ("This file holds personal information (or nobody was sure), so relationships wait for a "
                      "local decision model. Entities were kept.")
    return target, ""


def _overlap(a: Mention, b: Mention) -> bool:
    return a.chunk == b.chunk and a.start < b.end and b.start < a.end


def find_mentions(o: Ontology, texts: list[str], threshold: float) -> list[Mention]:
    raw: list[Mention] = []
    groups = o.label_groups()
    for group in groups + [{CATCH_ALL: CATCH_ALL_DESCRIPTION}]:
        for i, found in enumerate(extractor.entities(texts, group, threshold)):
            for hit in found:
                iri = "" if hit["label"] == CATCH_ALL else (o.class_for_label(hit["label"]) or "")
                if hit["label"] != CATCH_ALL and not iri:
                    continue
                if not str(hit.get("text", "")).strip() or hit.get("start") is None:
                    continue
                raw.append(Mention(i, int(hit["start"]), int(hit["end"]), str(hit["text"]).strip()[:300], iri,
                                   float(hit.get("confidence", 0.0))))
    kept: list[Mention] = []
    for m in sorted(raw, key=lambda x: (-x.score, x.class_iri == "")):  # typed beats catch-all on ties
        clash = next((k for k in kept if _overlap(k, m)), None)
        if clash is None:
            kept.append(m)
        elif m.class_iri and clash.class_iri and m.class_iri != clash.class_iri and clash.score - m.score < CLASS_MARGIN:
            clash.alternatives.append((m.class_iri, m.score))
    return sorted(kept, key=lambda x: (x.chunk, x.start))


def _ask(state: dict, questions: dict, target) -> dict:
    answers, _, _ = jev.system_one(state, questions, target=target)
    return answers


def confirm_classes(o: Ontology, mentions: list[Mention], texts: list[str], target: jev.Target | None) -> None:
    """Jev picks between close classes for a span. Its options are only the classes GLiNER2 offered."""
    by_chunk: dict[int, list[Mention]] = {}
    for m in mentions:
        if m.alternatives:
            by_chunk.setdefault(m.chunk, []).append(m)
    for chunk, ms in by_chunk.items():
        questions, options = {}, {}
        for n, m in enumerate(ms):
            classes = [m.class_iri] + [c for c, _ in sorted(m.alternatives, key=lambda x: -x[1])][:4]
            room = 50 if target is not None and target.flavour == "laya" else 160
            opts = {f"c{i}": f"{o.label(c)}: {(o.classes[c].get('definition') or '')[:room]}" for i, c in enumerate(classes)}
            opts["none"] = "None of these fits"
            questions[f"q{n}"] = jev.choice(f"In `text`, what is \"{m.text}\"?", opts)
            options[f"q{n}"] = classes
        answers = _ask({"text": texts[chunk]}, questions, target)
        for n, m in enumerate(ms):
            choice, conf = jev.picked(answers, f"q{n}")
            if choice and choice.startswith("c") and conf >= 0.5:
                m.class_iri, m.method = options[f"q{n}"][int(choice[1:])], "gliner2+jev"
            elif choice == "none" and conf >= 0.5:
                m.class_iri = ""  # becomes a candidate rather than a wrong type


def _pairs(ms: list[Mention], limit: int) -> list[tuple[Mention, Mention]]:
    typed = [m for m in ms if m.class_iri]
    pairs = [(a, b) for i, a in enumerate(typed) for b in typed[i + 1:] if a.text.casefold() != b.text.casefold()]
    return sorted(pairs, key=lambda p: abs(p[0].start - p[1].start))[:limit]


def group_options(options: list[Option], size: int) -> list[tuple[str, list[Option]]]:
    """Groups for the first of two questions: direct relationships and roles apart, at most size
    each, labelled with what they hold so the model can find the right one."""
    direct = [x for x in options if x.property_iri]
    roles = [x for x in options if x.role_iri]
    out: list[tuple[str, list[Option]]] = []
    for i in range(0, len(direct), size):
        g = direct[i:i + size]
        names = ", ".join(dict.fromkeys(x.label.split(" ", 1)[1].rsplit(" ", 1)[0] for x in g))
        out.append((f"a direct link: {names}", g))
    for i in range(0, len(roles), size):
        g = roles[i:i + size]
        who = g[0].label.split(" ", 1)[0]
        names = ", ".join(x.label.split(" is ", 1)[1].rsplit(" in ", 1)[0] for x in g)
        out.append((f"{who}'s role: {names}", g))
    return out


def _question(o: Ontology, a: Mention, b: Mention, opts: dict[str, str]) -> dict:
    opts = opts | {"none": "text doesn't say", "other": "a relationship not listed"}
    return jev.choice(f"In `text`, A is \"{a.text}\" ({o.label(a.class_iri)}) and B is \"{b.text}\" "
                      f"({o.label(b.class_iri)}). How is A related to B?", opts)


def find_relations(o: Ontology, mentions: list[Mention], texts: list[str], target: jev.Target | None, max_pairs: int,
                   min_conf: float) -> tuple[list[tuple[Mention, Mention, Option, float]], list[tuple[Mention, Mention]]]:
    """(relations found, pairs where the text states a relationship the ontology lacks)."""
    found, other = [], []
    size = group_size(target.flavour if target is not None else get_settings().decision_flavour)
    by_chunk: dict[int, list[Mention]] = {}
    for m in mentions:
        by_chunk.setdefault(m.chunk, []).append(m)
    for chunk, ms in by_chunk.items():
        pending: list[tuple[str, Mention, Mention, list[Option], list[list[Option]] | None]] = []
        questions = {}
        for n, (a, b) in enumerate(_pairs(ms, max_pairs)):
            options = o.relation_options(a.class_iri, b.class_iri)
            if not options:
                continue
            if len(options) <= size:
                questions[f"r{n}"] = _question(o, a, b, {x.key: x.label for x in options})
                pending.append((f"r{n}", a, b, options, None))
            else:  # two steps: which group of options, then which option
                labelled = group_options(options, size)
                groups = [g for _, g in labelled]
                questions[f"r{n}"] = _question(o, a, b, {f"g{i}": label for i, (label, _) in enumerate(labelled)})
                pending.append((f"r{n}", a, b, options, groups))
        if not questions:
            continue
        state = {"text": texts[chunk]}
        answers = _ask(state, questions, target)
        second = {}
        for key, a, b, options, split in pending:
            choice, conf = jev.picked(answers, key)
            if choice == "other" and conf >= min_conf:
                other.append((a, b))
            elif split is None and choice and choice.startswith("p") and conf >= min_conf:
                found.append((a, b, next(x for x in options if x.key == choice), conf))
            elif split is not None and choice and choice.startswith("g") and conf >= min_conf:
                group = split[int(choice[1:])]
                second[key] = (a, b, group, _question(o, a, b, {x.key: x.label for x in group}))
        if second:
            answers = _ask(state, {k: v[3] for k, v in second.items()}, target)
            for key, (a, b, group, _) in second.items():
                choice, conf = jev.picked(answers, key)
                if choice == "other" and conf >= min_conf:
                    other.append((a, b))
                elif choice and choice.startswith("p") and conf >= min_conf:
                    found.append((a, b, next(x for x in group if x.key == choice), conf))
    return found, other


def propose(db: DB, o: Ontology, kind: str, label: str, chunk_id: str, domain: str = "", range_: str = "") -> None:
    norm = resolve.normalise(label)
    c = db.scalar(select(OntologyCandidate).where(
        OntologyCandidate.kind == kind, OntologyCandidate.norm_label == norm, OntologyCandidate.domain_iri == domain,
        OntologyCandidate.range_iri == range_, OntologyCandidate.ontology_version == o.version,
        OntologyCandidate.status == "open"))
    if c is None:
        c = OntologyCandidate(kind=kind, label=label[:300], norm_label=norm, domain_iri=domain, range_iri=range_,
                              evidence=[], occurrences=0, ontology_version=o.version)
        db.add(c)
    evidence = list(c.evidence or [])
    if chunk_id not in evidence and len(evidence) < 20:
        evidence.append(chunk_id)
    c.evidence, c.occurrences = evidence, (c.occurrences or 0) + 1


def extraction_key(doc: Document, target_ok: bool) -> str:
    s = get_settings()
    return hashlib.sha256(f"{doc.index_key}:{s.ontology_version}:{EXTRACTOR_VERSION}:{s.extract_threshold}:"
                          f"{s.extract_relation_threshold}:{target_ok}".encode()).hexdigest()


def run(db: DB, doc: Document) -> bool:
    """Extract for one document. Returns False when it was already up to date."""
    s = get_settings()
    o = load()
    target, blocked = decision_target(doc)
    key = extraction_key(doc, not blocked)
    if doc.extract_key == key and doc.stage in ("extracted", "graphed"):
        return False
    chunks = db.scalars(select(Chunk).where(Chunk.document_id == doc.id).order_by(Chunk.idx)).all()
    texts = [c.text for c in chunks]
    mentions = find_mentions(o, texts, s.extract_threshold) if texts else []
    tags = extractor.classify(texts, o.tag_schemes(), s.extract_threshold) if texts else []
    relations: list = []
    other: list = []
    if not blocked and mentions:
        confirm_classes(o, mentions, texts, target)
        relations, other = find_relations(o, mentions, texts, target, s.extract_max_pairs, s.extract_relation_threshold)

    chunk_ids = [c.id for c in chunks]
    for table in (RelationAssertion, EntityMention, ChunkTag):
        db.execute(delete(table).where(table.chunk_id.in_(chunk_ids)))
    concept_by_label = {(scheme, c["label"]): c["iri"] for s_iri, cs in o.concepts.items()
                        for scheme in [o.label(s_iri)] for c in cs}
    for i, found in enumerate(tags):
        for scheme, labels in found.items():
            for t in labels:
                iri = concept_by_label.get((scheme, t["label"]))
                if iri:
                    db.add(ChunkTag(chunk_id=chunk_ids[i], document_id=doc.id, concept_iri=iri,
                                    confidence=float(t.get("confidence", 0.0))))
    for m in mentions:
        if not m.class_iri:
            propose(db, o, "class", m.text, chunk_ids[m.chunk])
            continue
        row = EntityMention(chunk_id=chunk_ids[m.chunk], document_id=doc.id, source_id=doc.source_id, start=m.start,
                            end=m.end, surface=m.text, class_iri=m.class_iri, score=m.score, method=m.method,
                            entity_key=resolve.entity_key(m.class_iri, m.text, o.is_a(m.class_iri, "pbo:Party")))
        db.add(row)
        db.flush()
        m.id = row.id
    model = "jev" if not blocked else ""
    for a, b, option, conf in relations:
        subject, obj = (b, a) if option.reverse else (a, b)
        db.add(RelationAssertion(chunk_id=chunk_ids[a.chunk], document_id=doc.id, source_id=doc.source_id,
                                 subject_mention_id=subject.id, object_mention_id=obj.id,
                                 property_iri=option.property_iri, role_iri=option.role_iri, confidence=conf,
                                 model=model))
    for a, b in other:
        propose(db, o, "relation", f"{o.label(a.class_iri)} to {o.label(b.class_iri)}", chunk_ids[a.chunk],
                a.class_iri, b.class_iri)
    doc.extract_key, doc.stage = key, "extracted"
    if blocked and mentions:
        doc.status, doc.note = "partial", blocked[:1000]
    elif doc.status == "partial":
        doc.status, doc.note = "ok", ""
    log.info("extracted %s %s: %d mentions, %d relations, %d tags", doc.source_type, doc.source_id,
             len([m for m in mentions if m.class_iri]), len(relations), sum(len(v) for t in tags for v in t.values()))
    return True
