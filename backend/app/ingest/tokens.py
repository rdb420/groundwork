"""Token counting for chunk sizes. The embedding sidecar's three models (MiniLM, SPLADE,
ColBERTv2) all use BERT's uncased WordPiece vocabulary, so one tokenizer, bundled here, counts for
all of them. Counting locally keeps the chunker fast; it tries many splits per document."""
from functools import lru_cache
from pathlib import Path

from tokenizers import Tokenizer

TOKENIZER = Path(__file__).parent / "data" / "bert-base-uncased-tokenizer.json"


@lru_cache
def _tok() -> Tokenizer:
    return Tokenizer.from_file(str(TOKENIZER))


def count(text: str) -> int:
    """Tokens in text, without the [CLS]/[SEP] a model adds (those sit outside the chunk budget)."""
    return len(_tok().encode(text, add_special_tokens=False).ids) if text else 0


def split_at(text: str, n: int) -> tuple[str, str]:
    """The longest prefix of text with at most n tokens, and the rest. Splits between tokens."""
    enc = _tok().encode(text, add_special_tokens=False)
    if len(enc.ids) <= n:
        return text, ""
    cut = enc.offsets[n][0]
    # Prefer to cut at the last space before the token boundary, so words aren't broken mid-piece.
    space = text.rfind(" ", 0, cut)
    if space > 0 and count(text[:space]) <= n:
        cut = space
    return text[:cut].rstrip(), text[cut:].lstrip()
