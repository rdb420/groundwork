"""Pin a version of rdb420/property_ontology into Groundwork.

The ontology repo's build script writes model.yaml; this turns it into the JSON snapshot the
pipeline reads (no YAML dependency at runtime) with a checksum, under backend/ontology/pbo-<version>/.
Run it with PyYAML supplied just for the run:

    cd backend
    gh api repos/rdb420/property_ontology/contents/property-ontology/model.yaml?ref=<commit> \\
        --jq .content | base64 -d > /tmp/model.yaml
    uv run --with pyyaml python -m scripts.vendor_ontology /tmp/model.yaml --version 0.1.0 --ref <commit>

Then set GW_ONTOLOGY_VERSION to the new version and reprocess from the extraction stage.
Released versions of the ontology never change, so neither does a vendored snapshot.
"""
import argparse
import hashlib
import json
from pathlib import Path

import yaml  # supplied by `uv run --with pyyaml`

KEEP = ("iri", "kind", "label", "definition", "domain", "range", "in_scheme", "also_instance_of", "rdf_type",
        "status", "characteristics")


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("model_yaml")
    p.add_argument("--version", required=True)
    p.add_argument("--ref", required=True, help="the property_ontology commit the file came from")
    args = p.parse_args()
    raw = Path(args.model_yaml).read_bytes()
    model = yaml.safe_load(raw)
    terms = [{k: t.get(k) for k in KEEP if t.get(k) is not None} for t in model["terms"]
             if t.get("status", "accepted") == "accepted"]
    axioms = []
    for a in model.get("axioms", []):
        if a.get("status", "accepted") != "accepted":
            continue
        if a.get("type") == "subClassOf":
            axioms.append({"type": "subClassOf", "subject": a["subject"], "object": a["object"]})
        elif a.get("type") == "disjointClasses":
            axioms.append({"type": "disjointClasses", "members": a["members"]})
    patterns = [{"name": x["name"], "description": x.get("description", "")} for x in model.get("patterns", [])]
    snapshot = {"version": args.version, "ref": args.ref, "source_sha256": hashlib.sha256(raw).hexdigest(),
                "namespace": "https://ontology.property.local/pbo#", "terms": terms, "axioms": axioms,
                "patterns": patterns}
    out = Path(__file__).resolve().parents[1] / "ontology" / f"pbo-{args.version}"
    out.mkdir(parents=True, exist_ok=True)
    data = json.dumps(snapshot, indent=1, ensure_ascii=False, sort_keys=True).encode()
    (out / "model.json").write_bytes(data)
    (out / "model.json.sha256").write_text(hashlib.sha256(data).hexdigest() + "\n")
    kinds: dict[str, int] = {}
    for t in terms:
        kinds[t["kind"]] = kinds.get(t["kind"], 0) + 1
    print(f"wrote {out / 'model.json'}: {kinds}, {len(axioms)} axioms")


if __name__ == "__main__":
    main()
