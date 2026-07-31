"""Garde-fou déterministe contre la restitution du corpus privé."""

from __future__ import annotations

import re


MAX_VERBATIM_WORDS = 20
WORD_RE = re.compile(r"[\wÀ-ÖØ-öø-ÿ]+(?:['’\-][\wÀ-ÖØ-öø-ÿ]+)*", re.UNICODE)


def normalized_words(text: str) -> list[str]:
    return [match.casefold() for match in WORD_RE.findall(text or "")]


def has_long_verbatim_overlap(
    answer: str,
    contexts: list[str],
    *,
    max_words: int = MAX_VERBATIM_WORDS,
) -> bool:
    """Détecte toute séquence copiée de plus de ``max_words`` mots."""
    if max_words < 1:
        raise ValueError("max_words doit être strictement positif")
    window = max_words + 1
    answer_words = normalized_words(answer)
    if len(answer_words) < window:
        return False
    answer_windows = {
        tuple(answer_words[index:index + window])
        for index in range(len(answer_words) - window + 1)
    }
    for context in contexts:
        words = normalized_words(context)
        for index in range(len(words) - window + 1):
            if tuple(words[index:index + window]) in answer_windows:
                return True
    return False


def short_excerpt(text: str, *, max_words: int = MAX_VERBATIM_WORDS) -> str:
    """Produit l'extrait public court sans dépasser la limite verbatim."""
    words = " ".join((text or "").split()).split(" ")
    excerpt = " ".join(words[:max_words]).strip()
    return excerpt + ("…" if len(words) > max_words else "")
