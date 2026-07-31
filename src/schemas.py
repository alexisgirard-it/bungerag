"""Contrats de donnees communs a tous les chemins du pipeline."""

from __future__ import annotations

from typing import Literal, TypedDict

from citations import CitationValidation


Mode = Literal["direct", "panoramique"]
AbstentionReason = Literal[
    "pre-generation", "llm", "citation-validation", "output-validation"
]


class Source(TypedDict):
    titre: str
    pages: str
    score: float
    extrait: str


class RAGResult(TypedDict):
    answer: str
    sources: list[Source]
    contexts: list[str]
    abstained: AbstentionReason | None
    mode: Mode
    question_en: str | None
    sous_questions: list[str]
    top_score: float
    timings: dict[str, float]
    citation_validation: CitationValidation
    config_id: str


RESULT_KEYS = frozenset(RAGResult.__annotations__)


def make_result(
    *,
    answer: str,
    sources: list[Source],
    contexts: list[str],
    abstained: AbstentionReason | None,
    mode: Mode,
    question_en: str | None,
    sous_questions: list[str],
    top_score: float,
    timings: dict[str, float],
    citation_validation: CitationValidation,
    config_id: str,
) -> RAGResult:
    """Construit un resultat complet sans valeurs mutables partagees."""
    return {
        "answer": answer,
        "sources": list(sources),
        "contexts": list(contexts),
        "abstained": abstained,
        "mode": mode,
        "question_en": question_en,
        "sous_questions": list(sous_questions),
        "top_score": float(top_score),
        "timings": {key: float(value) for key, value in timings.items()},
        "citation_validation": citation_validation.copy(),
        "config_id": config_id,
    }
