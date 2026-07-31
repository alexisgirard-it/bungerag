"""Extension (b) - routeur + decomposition des questions panoramiques.

Le RAG simple excelle sur les questions precises et plafonne sur les
panoramiques (« resume la philosophie de Bunge ») : 6 extraits ne couvrent
pas une oeuvre. Remede : eclater la question en sous-questions, recuperer
pour chacune, synthetiser le tout.

UN SEUL appel LLM utilitaire fait les trois taches : router
(direct/panoramique), decomposer et traduire (la jambe BM25 veut de
l'anglais). Le profil choisit explicitement Cerebras ou Ollama. Sortie JSON
stricte.
"""

import json
import re

from config import get_config
from generate import generate

PROMPT = """Tu prepares une question pour un systeme de recherche documentaire sur l'oeuvre du philosophe Mario Bunge.

Question : {question}

Etape 1 - CLASSIFIE :
- "direct" : la question porte sur UN concept/theme precis (une definition, une critique ciblee, un fait). La recherche documentaire directe suffira.
- "panoramique" : la question demande une vue d'ensemble, une synthese multi-themes, un parcours a travers l'oeuvre (resume general, "grandes lignes", comparaison de plusieurs domaines, evolution d'une pensee).

Etape 2 - si "panoramique", DECOMPOSE en 3 a 5 sous-questions PRECISES et complementaires qui, ensemble, couvrent la question (chacune doit etre trouvable dans des livres : concepts nommes, pas de meta-questions).

Reponds UNIQUEMENT avec ce JSON (rien d'autre) :
{{"mode": "direct"}}
ou
{{"mode": "panoramique", "sous_questions": [{{"fr": "...", "en": "..."}}, ...]}}"""

def _validated_route(value):
    if not isinstance(value, dict):
        raise ValueError("la sortie du routeur doit etre un objet JSON")
    mode = value.get("mode")
    if mode == "direct":
        return {"mode": "direct"}
    if mode != "panoramique":
        raise ValueError("mode de routage invalide")

    questions = value.get("sous_questions")
    if not isinstance(questions, list) or not 2 <= len(questions) <= 6:
        raise ValueError("le routeur doit produire entre 2 et 6 sous-questions")
    normalized = []
    for question in questions:
        if not isinstance(question, dict):
            raise ValueError("chaque sous-question doit etre un objet")
        fr, en = question.get("fr"), question.get("en")
        if not isinstance(fr, str) or not fr.strip():
            raise ValueError("sous-question francaise manquante")
        if not isinstance(en, str) or not en.strip():
            raise ValueError("traduction anglaise manquante")
        normalized.append({"fr": fr.strip(), "en": en.strip()})
    return {"mode": "panoramique", "sous_questions": normalized}


def analyse(question, backend=None):
    """Route la question, avec repli direct couvrant appel, parsing et schema."""
    backend = backend or get_config().router_backend
    try:
        raw = generate(PROMPT.format(question=question), max_tokens=1200,
                       backend=backend)
        match = re.search(r"\{.*\}", raw, re.S)
        if match is None:
            raise ValueError("aucun objet JSON dans la sortie du routeur")
        return _validated_route(json.loads(match.group(0)))
    except Exception as exc:
        # degradation gracieuse : au moindre doute, pipeline direct
        print(f"  [routeur indisponible ({type(exc).__name__}), mode direct]",
              flush=True)
        return {"mode": "direct"}

if __name__ == "__main__":
    import sys
    print(json.dumps(analyse(sys.argv[1]), ensure_ascii=False, indent=2))
