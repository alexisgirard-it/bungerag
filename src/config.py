"""Configuration explicite et reproductible du pipeline BungeRAG.

Les profils decrivent une configuration complete. Les anciennes variables
d'environnement restent acceptees comme surcharges, mais leur valeur est alors
incluse dans l'empreinte de configuration.
"""

from __future__ import annotations

import hashlib
import json
import os
from dataclasses import asdict, dataclass, replace


@dataclass(frozen=True)
class RAGConfig:
    """Parametres qui modifient le comportement observable du pipeline."""

    name: str
    table: str
    k_candidates: int
    k_final: int
    pano_k: int
    pano_per_question: int
    pano_final: int
    abstention_threshold: float
    generation_backend: str
    translator_backend: str
    router_backend: str

    def __post_init__(self) -> None:
        if not self.name.strip():
            raise ValueError("config.name ne peut pas etre vide")
        if not self.table.strip():
            raise ValueError("config.table ne peut pas etre vide")
        for field in ("k_candidates", "k_final", "pano_k",
                      "pano_per_question", "pano_final"):
            if getattr(self, field) <= 0:
                raise ValueError(f"config.{field} doit etre strictement positif")
        if self.k_final > self.k_candidates:
            raise ValueError("k_final ne peut pas depasser k_candidates")
        if not 0 <= self.abstention_threshold <= 1:
            raise ValueError("abstention_threshold doit etre compris entre 0 et 1")
        for field in ("generation_backend", "translator_backend", "router_backend"):
            if not getattr(self, field).strip():
                raise ValueError(f"config.{field} ne peut pas etre vide")

    def public_dict(self) -> dict:
        """Representation stable et sans secret, utilisable dans les rapports."""
        return asdict(self)

    @property
    def config_id(self) -> str:
        payload = json.dumps(
            self.public_dict(), sort_keys=True, separators=(",", ":")
        ).encode("utf-8")
        return hashlib.sha256(payload).hexdigest()[:12]


PUBLIC_V1 = RAGConfig(
    name="public_v1",
    table="bunge_512",
    k_candidates=12,
    k_final=5,
    pano_k=8,
    pano_per_question=3,
    pano_final=12,
    abstention_threshold=0.10,
    generation_backend="gemini",
    translator_backend="cerebras",
    router_backend="cerebras",
)

RESEARCH_40X6 = RAGConfig(
    name="research_40x6",
    table="bunge_512",
    k_candidates=40,
    k_final=6,
    pano_k=20,
    pano_per_question=3,
    pano_final=12,
    abstention_threshold=0.10,
    generation_backend="gemini",
    translator_backend="cerebras",
    router_backend="cerebras",
)

PROFILES = {
    PUBLIC_V1.name: PUBLIC_V1,
    RESEARCH_40X6.name: RESEARCH_40X6,
}


def get_config(profile: str | RAGConfig | None = None) -> RAGConfig:
    """Charge un profil et applique les surcharges d'environnement connues.

    ``LLM_BACKEND=ollama`` commute aussi, par defaut, la traduction et le
    routeur sur Ollama. Une execution annoncee locale ne contacte donc pas
    Cerebras silencieusement. Les deux utilitaires peuvent encore etre
    surcharges explicitement pour une experience documentee.
    """
    if isinstance(profile, RAGConfig):
        # Un objet explicite est deja la configuration finale. C'est essentiel
        # pour qu'une evaluation canonique ne soit pas alteree par le shell.
        return profile
    else:
        name = profile or os.environ.get("RAG_PROFILE", PUBLIC_V1.name)
        try:
            base = PROFILES[name]
        except KeyError as exc:
            choices = ", ".join(sorted(PROFILES))
            raise ValueError(f"profil RAG inconnu '{name}' (choix: {choices})") from exc

    generation_backend = os.environ.get("LLM_BACKEND", base.generation_backend)
    utility_default = "ollama" if generation_backend == "ollama" else None

    return replace(
        base,
        table=os.environ.get("BUNGE_TABLE", base.table),
        k_candidates=int(os.environ.get("RAG_K_CANDIDATES", base.k_candidates)),
        k_final=int(os.environ.get("RAG_K_FINAL", base.k_final)),
        pano_k=int(os.environ.get("RAG_PANO_K", base.pano_k)),
        pano_per_question=int(os.environ.get(
            "RAG_PANO_PER_QUESTION", base.pano_per_question)),
        pano_final=int(os.environ.get("RAG_PANO_FINAL", base.pano_final)),
        abstention_threshold=float(os.environ.get(
            "RAG_ABSTENTION_THRESHOLD", base.abstention_threshold)),
        generation_backend=generation_backend,
        translator_backend=os.environ.get(
            "RAG_TRANSLATOR_BACKEND", utility_default or base.translator_backend),
        router_backend=os.environ.get(
            "RAG_ROUTER_BACKEND", utility_default or base.router_backend),
    )
