"""The pinned property ontology (rdb420/property_ontology), read from the vendored JSON snapshot
backend/ontology/pbo-<GW_ONTOLOGY_VERSION>/model.json (see scripts/vendor_ontology.py).

It gives the extraction stage everything it may choose from:
- entity labels for GLiNER2: the concrete classes, with their definitions as descriptions, in
  groups of at most 15 (by top-level class). Participation and Role are left out: parties are
  typed as Person or Organisation, and roles come from the relation step (DEC-003).
- chunk tags: "kind" classes whose values are SKOS concepts (lease types, risk categories, ...)
  are tagged per chunk from their schemes, not found as spans (PAT-003).
- relation options between two classes: object properties whose domain and range admit them
  (a missing domain or range admits anything), plus the roles a party can hold in an agreement,
  asset, project or business, expressed through the Participation pattern.
"""
import hashlib
import json
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

from ..config import get_settings

ROOT = Path(__file__).resolve().parents[2] / "ontology"
PATTERN_PROPERTIES = {"pbo:hasParticipation", "pbo:participationContext", "pbo:participant", "pbo:inRole"}
NOT_SPANS = {"pbo:Participation", "pbo:Role", "pbo:MetricValue", "pbo:OutgoingAllocation"}
PARTY = "pbo:Party"
# Classes a party can hold a role in, from hasParticipation's definition (the domain is left open).
PARTICIPATION_CONTEXTS = ("pbo:Agreement", "pbo:PropertyAsset", "pbo:DevelopmentProject", "pbo:Business")
GROUP_SIZE = 15


class OntologyError(RuntimeError):
    pass


@dataclass
class Option:
    """One answer a relation question can have."""
    key: str  # short id used in the Jev question
    label: str  # what the decision model reads
    property_iri: str = ""  # a direct relation, subject -> object
    role_iri: str = ""  # or a role the party holds in the context, through Participation
    reverse: bool = False  # True when the property runs from the second mention to the first


@dataclass
class Ontology:
    version: str
    ref: str
    terms: dict[str, dict]
    parents: dict[str, set[str]]
    classes: dict[str, dict] = field(default_factory=dict)
    properties: dict[str, dict] = field(default_factory=dict)
    roles: dict[str, dict] = field(default_factory=dict)
    schemes: dict[str, dict] = field(default_factory=dict)
    concepts: dict[str, list[dict]] = field(default_factory=dict)  # scheme iri -> concepts
    kind_classes: set[str] = field(default_factory=set)

    def label(self, iri: str) -> str:
        return (self.terms.get(iri) or {}).get("label", iri.removeprefix("pbo:"))

    def ancestors(self, iri: str) -> set[str]:
        out, stack = {iri}, [iri]
        while stack:
            for p in self.parents.get(stack.pop(), ()):
                if p not in out:
                    out.add(p)
                    stack.append(p)
        return out

    def is_a(self, iri: str, ancestor: str | None) -> bool:
        return ancestor is None or ancestor in self.ancestors(iri)

    def top(self, iri: str) -> str:
        """The top-level pbo class above iri (itself if it has no pbo parent)."""
        chain = [a for a in self.ancestors(iri) if a.startswith("pbo:") and not self.parents.get(a)]
        return sorted(chain)[0] if chain else iri

    def span_classes(self) -> list[str]:
        return sorted(c for c in self.classes if c not in NOT_SPANS and c not in self.kind_classes)

    def label_groups(self) -> list[dict[str, str]]:
        """GLiNER2 label sets: {label: definition}, grouped by top-level class, at most 15 each."""
        by_top: dict[str, list[str]] = {}
        for c in self.span_classes():
            by_top.setdefault(self.top(c), []).append(c)
        groups: list[list[str]] = []
        current: list[str] = []
        for _, members in sorted(by_top.items(), key=lambda kv: -len(kv[1])):
            for i in range(0, len(members), GROUP_SIZE):
                part = members[i:i + GROUP_SIZE]
                if len(current) + len(part) > GROUP_SIZE:
                    groups.append(current)
                    current = []
                current += part
        if current:
            groups.append(current)
        return [{self.label(c): (self.classes[c].get("definition") or "")[:300] for c in g} for g in groups]

    def class_for_label(self, label: str) -> str | None:
        return next((c for c in self.classes if self.label(c) == label), None)

    def relation_options(self, a: str, b: str) -> list[Option]:
        """Every way the ontology lets mention A (class a) relate to mention B (class b)."""
        out: list[Option] = []
        for iri, p in sorted(self.properties.items()):
            if iri in PATTERN_PROPERTIES:
                continue
            dom, rng = p.get("domain"), p.get("range")
            if self.is_a(a, dom) and self.is_a(b, rng):
                out.append(Option(f"p{len(out)}", f"{self.label(a)} {p['label']} {self.label(b)}", property_iri=iri))
            if a != b and self.is_a(b, dom) and self.is_a(a, rng):
                out.append(Option(f"p{len(out)}", f"{self.label(b)} {p['label']} {self.label(a)}", property_iri=iri,
                                  reverse=True))
        for party, context, reverse in ((a, b, False), (b, a, True)):
            if self.is_a(party, PARTY) and any(self.is_a(context, c) for c in PARTICIPATION_CONTEXTS):
                for r_iri, role in sorted(self.roles.items()):
                    out.append(Option(f"p{len(out)}", f"{self.label(party)} is {role['label']} for this "
                                                      f"{self.label(context).lower()}", role_iri=r_iri, reverse=reverse))
        return out

    def tag_schemes(self) -> dict[str, list[str]]:
        """Chunk tags: for each kind class's scheme, the concept labels it can take."""
        return {self.label(s): [c["label"] for c in self.concepts[s]] for s in sorted(self.concepts)
                if self.concepts[s] and s != "pbo:RoleScheme"}


def _load(version: str) -> Ontology:
    path = ROOT / f"pbo-{version}" / "model.json"
    if not path.exists():
        raise OntologyError(f"Ontology {version} isn't vendored. Run scripts/vendor_ontology.py.")
    data = path.read_bytes()
    want = (path.parent / "model.json.sha256").read_text().strip()
    if hashlib.sha256(data).hexdigest() != want:
        raise OntologyError(f"Ontology {version} doesn't match its checksum; re-vendor it rather than editing it.")
    m = json.loads(data)
    terms = {t["iri"]: t for t in m["terms"]}
    parents: dict[str, set[str]] = {}
    for ax in m["axioms"]:
        if ax["type"] == "subClassOf" and ax["object"].startswith("pbo:"):
            parents.setdefault(ax["subject"], set()).add(ax["object"])
    o = Ontology(m["version"], m["ref"], terms, parents)
    for iri, t in terms.items():
        kind = t["kind"]
        if kind == "class":
            o.classes[iri] = t
        elif kind == "object_property":
            o.properties[iri] = t
        elif kind == "individual" and t.get("rdf_type") == "skos:ConceptScheme":
            o.schemes[iri] = t
        elif kind == "skos_concept":
            o.concepts.setdefault(t.get("in_scheme", ""), []).append(t)
            if t.get("also_instance_of"):
                o.kind_classes.add(t["also_instance_of"])
            if t.get("also_instance_of") == "pbo:Role":
                o.roles[iri] = t
    o.kind_classes.discard("pbo:Role")
    return o


@lru_cache
def load(version: str | None = None) -> Ontology:
    return _load(version or get_settings().ontology_version)
