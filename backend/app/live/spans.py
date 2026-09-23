"""Candidate phrases for labels. The decision model can't write text, so code proposes spans
taken word for word from what was said and the model picks one. A label is therefore always
the speaker's own words; the session reviewer tidies wording later."""
import re

FILLER = {"um", "uh", "er", "ah", "like", "basically", "just", "so", "yeah", "okay", "ok", "well",
          "actually", "really", "kind", "sort", "of", "you", "know", "i", "mean"}
STOP = FILLER | {"the", "a", "an", "and", "or", "but", "to", "then", "it", "that", "this", "we", "they",
                 "he", "she", "is", "are", "was", "be", "in", "on", "at", "for", "with", "from", "by",
                 "if", "when", "our", "my", "their", "there", "what", "which", "who"}
SPLIT = re.compile(r"[,.;:!?]|\b(?:and then|then|after that|because|but|so that|so|once|when|before|after)\b", re.I)


def _clean(words: list[str]) -> list[str]:
    while words and words[0].lower().strip("'\"") in STOP:
        words = words[1:]
    while words and words[-1].lower().strip("'\"") in STOP:
        words = words[:-1]
    return words


def candidates(text: str, limit: int = 18) -> list[str]:
    seen, out = set(), []

    def add(ws, least=1):
        ws = _clean(ws)
        if not (least <= len(ws) <= 10):
            return
        phrase = " ".join(ws).strip(" '\"")
        key = phrase.lower()
        if phrase and key not in seen:
            seen.add(key)
            out.append(phrase[0].upper() + phrase[1:])

    clauses = [c.split() for c in SPLIT.split(text) if c and c.strip()]
    for c in clauses:  # whole clauses first: usually the best label
        add(c)
    # then shorter windows, taking turns between clauses so a long first clause can't crowd out the rest
    per_clause = [[c[i:i + n] for n in (4, 3, 5, 2, 6) for i in range(0, max(0, len(c) - n) + 1)] for c in clauses]
    for step in range(max((len(p) for p in per_clause), default=0)):
        for windows in per_clause:
            if step < len(windows):
                add(windows[step], least=2)
            if len(out) >= limit:
                return out
    return out[:limit]


def actor_candidates(text: str, limit: int = 18) -> list[str]:
    """Short phrases that could name a person, role, team or organisation: "the tenant", "Dean",
    "the bank", "accounts team". Names of outside parties become pool labels, so they must be short."""
    words = [w.strip(",.;:!?\"'()") for w in text.split()]
    seen: set[str] = set()
    named: list[str] = []
    other: list[str] = []
    for n in (1, 2, 3):
        for i in range(0, max(0, len(words) - n) + 1):
            ws = _clean(words[i:i + n])
            if len(ws) != n or any(w.lower() in STOP for w in ws):
                continue
            phrase = " ".join(ws)
            if phrase.lower() in seen:
                continue
            seen.add(phrase.lower())
            label = phrase[0].upper() + phrase[1:]
            (named if any(w[:1].isupper() for w in ws[1:] if w) or (i > 0 and ws[0][:1].isupper()) else other).append(label)
    return (named + other)[:limit]
