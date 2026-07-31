"""Validation structurelle des indices de citation produits par le LLM.

Ce module ne calcule aucune confiance et ne pretend pas prouver qu'une
affirmation est semantiquement soutenue. Il verifie uniquement que la reponse
cite au moins une source existante et qu'aucun indice n'est hors limites.
"""

from __future__ import annotations

import re
from typing import TypedDict


class CitationValidation(TypedDict):
    valid: bool
    indices: list[int]
    invalid_indices: list[int]
    reason: str | None


CITATION_RE = re.compile(r"\[\s*(-?\d+)\s*\]")
CITATION_FAILURE_ANSWER = (
    "Impossible de produire une reponse correctement sourcee a partir des "
    "extraits disponibles."
)


def validate_citations(
    answer: str,
    source_count: int,
    *,
    abstained: bool = False,
) -> CitationValidation:
    """Verifie la coherence des indices ``[n]`` avec les sources fournies."""
    if source_count < 0:
        raise ValueError("source_count ne peut pas etre negatif")

    indices = [int(raw) for raw in CITATION_RE.findall(answer or "")]
    invalid = sorted({i for i in indices if i < 1 or i > source_count})

    if invalid:
        return {
            "valid": False,
            "indices": indices,
            "invalid_indices": invalid,
            "reason": "invalid-indices",
        }
    if abstained:
        return {
            "valid": True,
            "indices": indices,
            "invalid_indices": [],
            "reason": "abstained",
        }
    if not indices:
        return {
            "valid": False,
            "indices": [],
            "invalid_indices": [],
            "reason": "missing-citation",
        }
    return {
        "valid": True,
        "indices": indices,
        "invalid_indices": [],
        "reason": None,
    }
