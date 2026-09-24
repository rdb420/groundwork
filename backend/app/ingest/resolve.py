"""Entity resolution, simple on purpose: the same class and the same normalised name are the same
thing. Good enough to join "YSH Pty Ltd" and "YSH" or "Mrs Sam Nguyen" and "Sam Nguyen"; anything
subtler waits for a person in the graph."""
import re
import uuid

NAMESPACE = uuid.UUID("0c7f6a52-3b1e-5d4a-9f2c-7e8d1a2b3c4d")
ORG_SUFFIXES = re.compile(r"\b(pty\.?\s*ltd\.?|pty\.?\s*limited|limited|ltd\.?|inc\.?|incorporated|p/l)$")
HONORIFICS = re.compile(r"^(mr|mrs|ms|miss|mx|dr|prof)\.?\s+")


def normalise(name: str, class_iri: str = "", is_party: bool = False) -> str:
    n = " ".join(re.sub(r"[^\w\s&/-]", " ", name.casefold()).split())
    n = re.sub(r"^the\s+", "", n)
    if is_party:
        n = ORG_SUFFIXES.sub("", HONORIFICS.sub("", n)).strip()
    return n or name.casefold().strip()


def entity_key(class_iri: str, name: str, is_party: bool = False) -> str:
    return str(uuid.uuid5(NAMESPACE, f"{class_iri}|{normalise(name, class_iri, is_party)}"))
